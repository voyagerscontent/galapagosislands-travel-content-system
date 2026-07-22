"""
Phase 2 — Constrained restructurer (Claude Sonnet).

Claude is used ONLY here, and only to REWORD text that Phase 1 already flagged.
It never sees the whole document at once, never invents facts, and every one of
its outputs passes back through the deterministic fact-safety guard before it is
accepted. This keeps the "no hallucination" contract: the model may vary form,
never substance.

Pipeline per flagged span:
  1. Build a Markov cadence-seed + paragraph-shape suggestion from the span's own
     words + the human travel corpus (restructurer/markov.py).
  2. Send the span + the NON-DEVIATION system prompt + the Markov material to
     Claude Sonnet (low temperature).
  3. Run factguard.check(original_span, rewrite):
        - HARD FAIL (new number/entity) -> re-prompt up to verify_max_passes.
        - still failing -> keep ORIGINAL span, mark needs_human_review.
        - MAJOR CHANGE (fact dropped) -> accept but wrap in light-blue highlight
          so a human editor can verify.
  4. Stitch accepted rewrites back into the full document by character offset.

Then the caller re-runs Phase 1 to confirm flags cleared (acceptance test).

Model access:
  - Uses the Anthropic Messages API. Set ANTHROPIC_API_KEY.
  - Model id configurable via PB_CLAUDE_MODEL (default: claude-sonnet-4-5).
  - If no key is present, runs in DRY_RUN mode: returns original spans wrapped
    with a note, so the pipeline is testable end-to-end without spending tokens.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from .markov import MarkovExtender
from . import factguard

# Default Claude Sonnet model. Override with PB_CLAUDE_MODEL.
# Available Sonnet ids (as of build): claude-sonnet-5, claude-sonnet-4-6,
# claude-sonnet-4-5-20250929.
CLAUDE_MODEL = os.environ.get("PB_CLAUDE_MODEL", "claude-sonnet-4-6")

# Light-blue highlight wrappers. HTML span for web/n8n; markers for plain text.
HL_OPEN_HTML = '<span class="pb-review" style="background-color:#cfe8ff">'
HL_CLOSE_HTML = "</span>"
HL_OPEN_MD = "[[PB-REVIEW]]"
HL_CLOSE_MD = "[[/PB-REVIEW]]"

# ---------------------------------------------------------------------------
# The non-deviation system prompt. This is HARDCODED and versioned. Claude is
# given no latitude beyond breaking the mechanical pattern while preserving
# every fact. Edits to behaviour happen HERE, in source control, not at runtime.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a constrained text-restructuring tool, NOT a writer with creative freedom.

You will receive ONE short flagged text span at a time, plus the exact mechanical
pattern(s) a deterministic detector found in it. Your ONLY job is to break those
patterns while preserving 100% of the meaning.

NON-DEVIATION RULES (violating any is a failure):
1. DO NOT add any fact, name, place, number, date, price, or claim that is not
   already present in the span. Zero new information.
2. DO NOT remove any fact, name, place, number, date, or price that IS present.
   Preserve every entity and every quantity exactly (you may spell a number in
   words, e.g. "3" -> "three", but never change its value).
3. DO NOT add filler, fluff, marketing adjectives, or padding to hit a length.
4. Preserve the original language and tense. If the span is Spanish, answer in
   Spanish. If English, English.

WHAT YOU MUST DO (this is why you exist):
- Break the detected pattern. If sentences were uniform in length, make them
  deliberately UNEVEN. This is mandatory: include at least one VERY SHORT
  sentence (2-5 words) AND at least one LONG sentence (18+ words) in your
  rewrite, so the length variation (burstiness) is high. Do NOT make every
  sentence a similar length. A one- or two-word sentence fragment is allowed if
  it preserves meaning.
- If sentence openings repeated, start each sentence differently.
- If paragraph structure was uniform, VARY it: use the suggested paragraph shape
  (number of paragraphs and sentences each) as a target, without adding content.
- If formulaic connectives (Moreover, Furthermore, Additionally, In conclusion)
  were used, remove or replace them with natural phrasing.
- You are given MARKOV CADENCE SEEDS drawn from the text's own words and a human
  travel corpus. Use them ONLY as inspiration for rhythm and natural connective
  variety. They are NOT facts to insert. Never state anything from a seed as a
  claim about the subject.

OUTPUT FORMAT:
Return ONLY the rewritten span as plain text. No preamble, no explanation, no
quotes around it, no markdown fences."""

USER_TEMPLATE = """FLAGGED SPAN (rewrite this, break the pattern, keep every fact):
---
{span}
---

DETECTED PATTERNS TO BREAK:
{reasons}

TARGET PARAGRAPH SHAPE (approximate, do NOT pad to reach it):
{shape}

MARKOV CADENCE SEEDS (rhythm/connective inspiration only — NOT facts):
{seeds}

Rewrite the span now. Output only the rewritten text."""


@dataclass
class SpanResult:
    start: int
    end: int
    original: str
    rewrite: str
    accepted: bool
    needs_human_review: bool
    major_change: bool
    factors: List[str] = field(default_factory=list)
    guard_reason: str = ""
    passes: int = 0


@dataclass
class RestructureResult:
    dry_run: bool
    span_results: List[SpanResult] = field(default_factory=list)
    output_text: str = ""          # plain text with [[PB-REVIEW]] markers
    output_html: str = ""          # HTML with light-blue highlight spans
    needs_human_review: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# --- Claude call -----------------------------------------------------------
def _live_enabled() -> bool:
    """Live mode when an API key is present OR the credential proxy is in use
    (PB_USE_PROXY=1, with the x-api-key injected by the HTTPS proxy)."""
    return bool(os.environ.get("ANTHROPIC_API_KEY")) or os.environ.get("PB_USE_PROXY") == "1"


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _payload(system: str, user: str, temperature: float) -> dict:
    return {
        "model": CLAUDE_MODEL,
        "max_tokens": 1024,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }


def _extract(data: dict) -> str:
    return "".join(
        block.get("text", "") for block in data.get("content", [])
        if block.get("type") == "text"
    ).strip()


def _call_via_curl(payload: dict) -> Optional[str]:
    """Transport used behind the credential proxy (curl trusts the proxy CA)."""
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        body_path = f.name
    try:
        proc = subprocess.run(
            ["curl", "-sS", ANTHROPIC_URL,
             "-H", f"anthropic-version: {ANTHROPIC_VERSION}",
             "-H", "content-type: application/json",
             "-H", f"x-api-key: {os.environ.get('ANTHROPIC_API_KEY', 'proxy-injected')}",
             "-d", f"@{body_path}"],
            capture_output=True, text=True, timeout=90,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"curl failed: {proc.stderr[:400]}")
        return _extract(json.loads(proc.stdout))
    finally:
        try:
            os.unlink(body_path)
        except OSError:
            pass


def _call_via_requests(payload: dict) -> Optional[str]:
    """Transport for direct ANTHROPIC_API_KEY use (no intercepting proxy)."""
    import requests
    headers = {
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
        "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
    }
    resp = requests.post(ANTHROPIC_URL, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    return _extract(resp.json())


def _call_claude(system: str, user: str, temperature: float = 0.4) -> Optional[str]:
    """Call the Claude Messages API. Uses curl when behind the credential proxy
    (PB_USE_PROXY=1), otherwise plain requests with a direct ANTHROPIC_API_KEY."""
    if not _live_enabled():
        return None
    payload = _payload(system, user, temperature)
    if os.environ.get("PB_USE_PROXY") == "1":
        return _call_via_curl(payload)
    return _call_via_requests(payload)


def _bucket_keywords(text: str) -> List[str]:
    """Pick corpus buckets by cheap keyword match so Markov stays on-topic."""
    low = text.lower()
    kws = []
    for k in ["galapagos", "cruise", "antarctica", "peru", "ecuador", "amazon",
              "wildlife", "weather", "planning", "health"]:
        if k in low:
            kws.append(k)
    kws.append("general")
    return kws


def restructure_span(span_text: str, reasons: List[str], factors: List[str],
                     max_passes: int, temperature: float = 0.4) -> SpanResult:
    mk = MarkovExtender(span_text, corpus_bucket_keywords=_bucket_keywords(span_text))
    seeds = mk.cadence_seeds(n=6, seed_salt=str(hash(span_text) & 0xffff))
    shape = mk.paragraph_shape(seed_salt=str(hash(span_text) & 0xffff))

    user = USER_TEMPLATE.format(
        span=span_text,
        reasons="\n".join(f"- {r}" for r in reasons) or "- generic mechanical rhythm",
        shape=json.dumps(shape),
        seeds="\n".join(f"- {s}" for s in seeds) or "- (none available)",
    )

    if not _live_enabled():
        # DRY RUN — no model. Keep original, mark for review so nothing silently ships.
        return SpanResult(
            start=0, end=0, original=span_text, rewrite=span_text, accepted=False,
            needs_human_review=True, major_change=False, factors=factors,
            guard_reason="DRY_RUN: ANTHROPIC_API_KEY not set; span unchanged.", passes=0,
        )

    best: Optional[str] = None
    last_reason = ""
    major = False
    for attempt in range(1, max_passes + 1):
        out = _call_claude(SYSTEM_PROMPT, user, temperature=temperature)
        if not out:
            last_reason = "empty model response"
            continue
        guard = factguard.check(span_text, out)
        if guard.ok:
            best = out
            major = guard.major_change
            last_reason = guard.reason
            return SpanResult(
                start=0, end=0, original=span_text, rewrite=out, accepted=True,
                needs_human_review=major, major_change=major, factors=factors,
                guard_reason=guard.reason, passes=attempt,
            )
        # hard fail -> tell Claude exactly what it broke and retry
        last_reason = guard.reason
        user = user + (
            f"\n\nATTEMPT {attempt} REJECTED by fact guard: {guard.reason}. "
            f"You MUST NOT introduce {guard.new_numbers + guard.new_entities}. "
            f"Rewrite again, changing only FORM, preserving every original fact."
        )

    # exhausted passes -> keep original, flag for human
    return SpanResult(
        start=0, end=0, original=span_text, rewrite=span_text, accepted=False,
        needs_human_review=True, major_change=True, factors=factors,
        guard_reason=f"Rejected after {max_passes} passes: {last_reason}", passes=max_passes,
    )


def restructure(text: str, flagged_spans: List[Dict], max_passes: int = 3,
                temperature: float = 0.4) -> RestructureResult:
    """
    flagged_spans: list of {start, end, factors, reasons} from Phase 1.
    Rewrites each span, then stitches back into the full document.
    """
    dry = not _live_enabled()
    results: List[SpanResult] = []

    # process spans in order; rewrite each independently
    ordered = sorted(flagged_spans, key=lambda s: s["start"])
    for sp in ordered:
        span_text = text[sp["start"]:sp["end"]]
        r = restructure_span(
            span_text, sp.get("reasons", []), sp.get("factors", []),
            max_passes=max_passes, temperature=temperature,
        )
        r.start, r.end = sp["start"], sp["end"]
        results.append(r)

    # stitch back-to-front so offsets stay valid
    out_plain = text
    out_html = text
    needs_review = False
    for r in sorted(results, key=lambda x: x.start, reverse=True):
        if r.accepted:
            plain_piece = r.rewrite
            html_piece = r.rewrite
            if r.major_change:
                plain_piece = f"{HL_OPEN_MD}{r.rewrite}{HL_CLOSE_MD}"
                html_piece = f"{HL_OPEN_HTML}{r.rewrite}{HL_CLOSE_HTML}"
                needs_review = True
        else:
            # not accepted: keep original but mark for human review (light blue)
            plain_piece = f"{HL_OPEN_MD}{r.original}{HL_CLOSE_MD}"
            html_piece = f"{HL_OPEN_HTML}{r.original}{HL_CLOSE_HTML}"
            needs_review = True
        out_plain = out_plain[:r.start] + plain_piece + out_plain[r.end:]
        out_html = out_html[:r.start] + html_piece + out_html[r.end:]

    return RestructureResult(
        dry_run=dry, span_results=results, output_text=out_plain,
        output_html=out_html, needs_human_review=needs_review,
    )


# Run the full pipeline via `python3 pipeline.py`, not this module directly.
