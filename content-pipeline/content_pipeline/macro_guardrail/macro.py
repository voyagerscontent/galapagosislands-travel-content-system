"""macro_guardrail — section-level structural entropy gate (gzip NCD).

STRICTLY MACRO. This module knows nothing about sentences, words, or vocabulary.
It looks only at the *shape* of a section: how paragraph lengths and their
"extensions" (sentence counts) vary. AI blocks are mechanically uniform — every
paragraph about the same size, built the same way — which is highly compressible
(low entropy). Human writing is bursty at the block level, so its structural
signature resists compression.

How it works
------------
1. Reduce the section to a STRUCTURED BYTE STRING that encodes ONLY paragraph
   token-lengths + sentence-counts (never the words) — so vocabulary can't
   interfere with the measurement.
2. Use gzip to compute the Normalized Compression Distance (NCD) between that
   signature and a maximally-uniform ("robotic") baseline of equal shape.
   NCD near 0  => the section's structure resembles the robotic baseline
                  (low entropy, uniform blocks) => REJECT.
   NCD higher  => the structure is far from uniform (bursty) => PASS.
3. On reject, the caller runs an LLM rewrite loop (max_retries=3).

No sentence-level or word-level logic lives here (that is micro_guardrail).
"""
from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

# Reject when structural NCD-from-uniform falls below this (too uniform/robotic).
# Calibrated so uniform blocks reject and bursty human blocks pass; tune per corpus.
DEFAULT_NCD_MIN = 0.28
MAX_RETRIES = 3

# Paragraphs split on blank lines; sentences on terminal punctuation. This is the
# ONLY structural parsing macro does — it never inspects the tokens themselves.
_PARA_SPLIT = re.compile(r"\n\s*\n+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _C(data: bytes) -> int:
    """Compressed size in bytes (gzip, deterministic — no timestamp)."""
    return len(gzip.compress(data, compresslevel=9, mtime=0))


def ncd(x: bytes, y: bytes) -> float:
    """Normalized Compression Distance (Cilibrasi & Vitányi).

    NCD(x, y) = (C(xy) - min(C(x), C(y))) / max(C(x), C(y)).  Range ~[0, 1+].
    0 => identical/maximally-similar structure; higher => more dissimilar.
    """
    cx, cy = _C(x), _C(y)
    cxy = _C(x + y)
    denom = max(cx, cy)
    return (cxy - min(cx, cy)) / denom if denom else 0.0


def paragraph_shape(section: str) -> List[tuple]:
    """(token_length, sentence_count) per non-empty paragraph. No vocabulary."""
    shape = []
    for para in _PARA_SPLIT.split(section.strip()):
        p = para.strip()
        if not p:
            continue
        tokens = len(p.split())
        sentences = len([s for s in _SENT_SPLIT.split(p) if s.strip()])
        shape.append((tokens, max(1, sentences)))
    return shape


def structured_byte_string(shape: List[tuple]) -> bytes:
    """Encode ONLY the length/extension pattern as run-length bytes.

    Each paragraph becomes a run of 'A' bytes as long as its token count, then a
    run of 'B' bytes as long as its sentence count, then a newline separator.
    Uniform paragraphs => repeated identical runs => very compressible.
    Varied paragraphs   => irregular runs => resists compression. Words never
    appear, so the gzip measurement reflects pure macro-burstiness.
    """
    out = bytearray()
    for tokens, sentences in shape:
        out += b"A" * tokens
        out += b"B" * sentences
        out += b"\n"
    return bytes(out)


def _uniform_baseline(shape: List[tuple]) -> bytes:
    """A same-size signature where every paragraph is the AVERAGE shape — the
    maximally uniform / 'robotic' block pattern to measure distance from."""
    n = len(shape) or 1
    avg_t = max(1, round(sum(t for t, _ in shape) / n))
    avg_s = max(1, round(sum(s for _, s in shape) / n))
    return structured_byte_string([(avg_t, avg_s)] * len(shape))


@dataclass
class MacroResult:
    passed: bool
    ncd: float
    threshold: float
    paragraphs: int
    shape: List[tuple] = field(default_factory=list)
    reason: str = ""


def evaluate(section: str, ncd_min: float = DEFAULT_NCD_MIN) -> MacroResult:
    """Score a section's macro-burstiness. passed=False => reject & rewrite."""
    shape = paragraph_shape(section)
    if len(shape) < 3:
        # too few paragraphs to judge block-rhythm; don't block the pipeline
        return MacroResult(True, 1.0, ncd_min, len(shape), shape,
                           "under 3 paragraphs — macro check skipped")
    sig = structured_byte_string(shape)
    base = _uniform_baseline(shape)
    score = ncd(sig, base)
    passed = score >= ncd_min
    return MacroResult(passed, round(score, 4), ncd_min, len(shape), shape,
                       "ok" if passed else
                       f"structural NCD {score:.3f} < {ncd_min} — uniform/robotic block pattern")


def enforce(section: str,
            rewrite: Callable[[str, MacroResult], str],
            ncd_min: float = DEFAULT_NCD_MIN,
            max_retries: int = MAX_RETRIES) -> tuple:
    """Evaluate; on reject call `rewrite(section, result)` up to max_retries.

    `rewrite` is the injected LLM rewrite step (kept out of this module so macro
    stays pure/deterministic and unit-testable). Returns (section, MacroResult,
    attempts). The final MacroResult may still be failing if retries ran out —
    the caller decides whether to accept-with-flag or escalate.
    """
    result = evaluate(section, ncd_min)
    attempts = 0
    while not result.passed and attempts < max_retries:
        attempts += 1
        section = rewrite(section, result)
        result = evaluate(section, ncd_min)
    return section, result, attempts
