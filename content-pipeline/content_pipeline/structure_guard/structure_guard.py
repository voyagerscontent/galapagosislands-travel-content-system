"""structure_guard — lock the optimized macro/micro skeleton through humanization.

After production generation runs macro_guardrail (paragraph-length burstiness) and
micro_guardrail (sentence-length CV), the draft has a deliberate SKELETON: a fixed
sequence of section HEADINGS and PROSE paragraphs with a bursty paragraph-length
distribution. The humanizer (LLM voice reconstruction) rewrites wording and, left
unconstrained, silently merges / splits / drops paragraphs and headings — undoing
the guardrails. A12 says it "may NOT remove structure", but that is a prompt wish,
and per the house rule *"LLMs cannot count — use code gates"* the skeleton has to
be enforced in CODE.

This module makes breaking the skeleton structurally impossible:

  * split_blocks / skeleton : decompose the optimized text into ordered BLOCKS —
    headings kept VERBATIM, prose paragraphs — and record the skeleton.
  * humanize_preserving      : humanize ONLY the prose blocks, ONE AT A TIME, and
    reassemble against the ORIGINAL skeleton. Heading text, block order and the
    paragraph COUNT are preserved by construction, not by asking the LLM nicely.
    Any paragraph break the humanizer sneaks INSIDE a block is flattened, so one
    prose block in is always one prose block out.
  * verify                   : a deterministic code gate that fails loudly if the
    humanized text lost / changed a heading, changed the prose-block count or the
    block order, or dropped macro-NCD / micro-CV below threshold.
  * guarded_humanization     : the full Step-4 pass — humanize_preserving, then
    micro_guardrail.enforce (restore CV within the locked paragraphs), then verify.

Stdlib + genpipe.core only. Deterministic.
"""
from __future__ import annotations

import re
from typing import Callable, Dict, List

from content_pipeline.common.tokenizer import paragraphs
from content_pipeline.macro_guardrail import macro as macro_guardrail
from content_pipeline.micro_guardrail import micro as micro_guardrail

# An ATX markdown heading line: 1-6 '#', a space, then text. Setext headings
# (underlined with === / ---) are rare in this pipeline's drafts and are treated
# as ordinary prose; ATX is what A03/A09 emit.
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")

Block = Dict[str, str]  # {"kind": "heading"|"prose", "text": str}


# --------------------------------------------------------------------------- #
# Decomposition
# --------------------------------------------------------------------------- #
def _is_heading(line: str) -> bool:
    return bool(_HEADING_RE.match(line))


def split_blocks(text: str) -> List[Block]:
    """Decompose text into ordered blocks.

    A heading line (ATX ``#``..``######``) is its OWN block, kept verbatim. Runs
    of consecutive non-blank, non-heading lines form one prose block. Blank lines
    are paragraph separators. This mirrors ``core.text.paragraphs`` for prose while
    peeling headings out so they can be passed through the humanizer untouched.
    """
    blocks: List[Block] = []
    buf: List[str] = []

    def _flush() -> None:
        if buf:
            para = "\n".join(buf).strip()
            if para:
                blocks.append({"kind": "prose", "text": para})
            buf.clear()

    for raw in str(text or "").splitlines():
        if raw.strip() == "":
            _flush()
            continue
        if _is_heading(raw):
            _flush()
            blocks.append({"kind": "heading", "text": raw.strip()})
            continue
        buf.append(raw)
    _flush()
    return blocks


def skeleton(text: str) -> List[Block]:
    """Alias of split_blocks — the ordered block list IS the skeleton."""
    return split_blocks(text)


def _collapse_internal_breaks(s: str) -> str:
    """Flatten any blank-line paragraph break the humanizer added INSIDE one prose
    block, so a single block can never fan out into several paragraphs downstream."""
    return re.sub(r"\n\s*\n+", " ", str(s or "")).strip()


def fingerprint(text: str) -> Dict:
    """Structural signature used by the gate: verbatim headings (in order), the
    block-kind sequence, and prose/paragraph counts."""
    blocks = split_blocks(text)
    return {
        "headings": [b["text"] for b in blocks if b["kind"] == "heading"],
        "kinds": [b["kind"] for b in blocks],
        "n_blocks": len(blocks),
        "n_prose": sum(1 for b in blocks if b["kind"] == "prose"),
        "n_paragraphs": len(paragraphs(text)),
    }


# --------------------------------------------------------------------------- #
# Skeleton-locked humanization
# --------------------------------------------------------------------------- #
def humanize_preserving(text: str, humanize_block_fn: Callable[[str], str]) -> str:
    """Humanize prose blocks in place against the original skeleton.

    ``humanize_block_fn`` is called ONCE PER PROSE BLOCK and must return the
    humanized version of that single paragraph. Headings are never passed to it —
    they are re-emitted verbatim. If the function returns empty/whitespace for a
    block, the ORIGINAL block is kept (a block is never dropped). Reassembles with
    blank-line separators, so ``fingerprint`` is invariant across the call except
    for the wording inside prose blocks.
    """
    out: List[str] = []
    for b in split_blocks(text):
        if b["kind"] == "heading":
            out.append(b["text"])
            continue
        rewritten = _collapse_internal_breaks(humanize_block_fn(b["text"]))
        out.append(rewritten if rewritten else b["text"])
    return "\n\n".join(out)


def verify(before: str, after: str) -> Dict:
    """Deterministic structure gate comparing humanized ``after`` to optimized
    ``before``. ``passed`` is True only when the skeleton is intact AND the macro
    / micro burstiness thresholds still hold."""
    fb, fa = fingerprint(before), fingerprint(after)
    headings_ok = fb["headings"] == fa["headings"]
    kinds_ok = fb["kinds"] == fa["kinds"]
    prose_ok = fb["n_prose"] == fa["n_prose"]
    para_ok = fb["n_paragraphs"] == fa["n_paragraphs"]

    macro = macro_guardrail.check(after)
    micro = micro_guardrail.check(after)

    reasons: List[str] = []
    if not headings_ok:
        reasons.append(
            f"headings changed: {fb['headings']!r} -> {fa['headings']!r}")
    if not kinds_ok:
        reasons.append("block order/kinds changed")
    if not prose_ok:
        reasons.append(
            f"prose-block count {fb['n_prose']} -> {fa['n_prose']}")
    if not para_ok:
        reasons.append(
            f"paragraph count {fb['n_paragraphs']} -> {fa['n_paragraphs']}")
    if not macro.passed:
        reasons.append(f"macro burstiness lost ({macro.reason})")
    if not micro.passed:
        reasons.append(f"micro burstiness lost ({micro.reason})")

    passed = headings_ok and kinds_ok and prose_ok and para_ok and macro.passed and micro.passed
    return {
        "passed": passed,
        "headings_ok": headings_ok,
        "kinds_ok": kinds_ok,
        "prose_count_ok": prose_ok,
        "paragraph_count_ok": para_ok,
        "macro_passed": macro.passed,
        "micro_passed": micro.passed,
        "macro_metric": macro.metric,
        "micro_metric": micro.metric,
        "reasons": reasons,
        "before": fb,
        "after": fa,
    }


def guarded_humanization(text: str, humanize_block_fn: Callable[[str], str]) -> Dict:
    """Full Step-4 humanization with the skeleton locked.

    1. humanize_preserving  — rewrite prose blocks only; headings + count locked.
    2. micro_guardrail.enforce — restore sentence-CV WITHIN the locked paragraphs.
    3. verify — deterministic gate vs the pre-humanization skeleton.

    macro cannot regress here (paragraph count is fixed and 1:1 block rewrites keep
    the length distribution bursty); the gate still checks it as a backstop.
    """
    humanized = humanize_preserving(text, humanize_block_fn)
    micro = micro_guardrail.enforce(humanized)
    final = micro.text
    report = verify(text, final)
    return {"text": final, "micro": micro, "structure": report}
