"""micro_guardrail — sentence-level burstiness via algorithmic split/combine.

Runs AFTER macro_guardrail has approved a section's block structure. It measures
the Coefficient of Variation (CV = stddev/mean) of sentence lengths (words per
sentence). Low CV = uniform, robotic rhythm. To raise it WITHOUT an LLM, it
either splits a long sentence in two or merges two short adjacent sentences —
purely mechanical edits.

HARD CONSTRAINT: it must NOT change the number of paragraphs or the structural
paragraph breaks established upstream. All edits happen inside a paragraph;
paragraphs are re-joined with their original blank-line separators and never
split, merged, added, or dropped. (Sentence count may change; paragraph count
may not.)
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import List, Optional

from content_pipeline.common import tokenizer as tok

# Human prose scatters sentence lengths; CV below this reads as mechanical.
DEFAULT_CV_MIN = 0.50
MAX_PASSES = 12          # safety bound on split/combine operations
# "short"/"long" are RELATIVE to the paragraph's own median sentence length, so
# uniform-medium prose is still actionable (the spec's split-long / combine-short
# intent, adaptive instead of fixed). Absolute floors keep edits sane.
MIN_SPLIT_WORDS = 12     # never split a sentence shorter than this
MIN_PART_WORDS = 3       # neither half of a split may be shorter than this

# Places a long sentence can be split into two independent-ish sentences.
_SPLIT_POINTS = re.compile(r"\s*(?:,\s+(?:and|but|so|yet|while|which|because|although)\b|;)\s+", re.I)


def cv(lengths: List[int]) -> float:
    if len(lengths) < 2:
        return 1.0
    m = statistics.mean(lengths)
    return statistics.pstdev(lengths) / m if m else 0.0


def _sentence_lengths(text: str) -> List[int]:
    return [tok.word_count(s) for s in tok.sentences(text)]


def measure(text: str) -> float:
    """CV of sentence lengths across the whole (multi-paragraph) text."""
    return cv(_sentence_lengths(text))


def _median(sentences: List[str]) -> float:
    return statistics.median([tok.word_count(s) for s in sentences]) if sentences else 0.0


def _split_long(sentences: List[str]) -> Optional[List[str]]:
    """Split a relatively-long sentence (>= median, >= MIN_SPLIT_WORDS) at a
    clause boundary into two sentences."""
    med = _median(sentences)
    order = sorted(range(len(sentences)), key=lambda i: -tok.word_count(sentences[i]))
    for i in order:
        s = sentences[i].strip()
        wc = tok.word_count(s)
        if wc < max(MIN_SPLIT_WORDS, med):
            break
        m = _SPLIT_POINTS.search(s)
        if not m:
            continue
        left, right = s[:m.start()].rstrip(" ,;"), s[m.end():].lstrip()
        if tok.word_count(left) < MIN_PART_WORDS or tok.word_count(right) < MIN_PART_WORDS:
            continue
        left = left + ("" if left.endswith((".", "!", "?")) else ".")
        right = right[0].upper() + right[1:] if right else right
        return sentences[:i] + [left, right] + sentences[i + 1:]
    return None


def _combine_short(sentences: List[str]) -> Optional[List[str]]:
    """Merge two ADJACENT relatively-short sentences (both <= median) into one."""
    med = _median(sentences)
    for i in range(len(sentences) - 1):
        a, b = sentences[i].strip(), sentences[i + 1].strip()
        if tok.word_count(a) <= med and tok.word_count(b) <= med:
            a_body = a.rstrip(".!?")
            b_body = b[0].lower() + b[1:] if b else b
            joiner = "; " if re.search(r"[,:;]", a_body) else ", and "
            merged = a_body + joiner + b_body
            return sentences[:i] + [merged] + sentences[i + 2:]
    return None


def _balance_paragraph(paragraph: str, target_cv: float, global_lengths: List[int]) -> str:
    """Apply one helpful split/combine inside a single paragraph if it lifts CV."""
    sents = tok.sentences(paragraph)
    if len(sents) < 2:
        return paragraph
    before = cv([tok.word_count(s) for s in sents])
    # try split first (adds a short next to a long -> more spread), else combine
    for op in (_split_long, _combine_short):
        cand = op(sents)
        if cand is None:
            continue
        after = cv([tok.word_count(s) for s in cand])
        if after > before:
            return " ".join(x.strip() for x in cand)
    return paragraph


@dataclass
class MicroResult:
    text: str
    cv_before: float
    cv_after: float
    threshold: float
    passes: int
    paragraphs_in: int
    paragraphs_out: int
    passed: bool
    note: str = ""


def enforce(text: str, cv_min: float = DEFAULT_CV_MIN, max_passes: int = MAX_PASSES) -> MicroResult:
    """Raise sentence-length CV to cv_min via split/combine, preserving paragraphs."""
    paras_in = tok.paragraphs(text)
    paras = list(paras_in)
    cv0 = measure(text)
    passes = 0
    while measure("\n\n".join(paras)) < cv_min and passes < max_passes:
        # each pass: try a mechanical edit in EVERY paragraph, keep the one that
        # lifts the GLOBAL CV most. Stop only when no paragraph offers a gain.
        best_i, best_p, best_cv = None, None, measure("\n\n".join(paras))
        for i, p in enumerate(paras):
            cand = _balance_paragraph(p, cv_min, [])
            if cand == p:
                continue
            trial = list(paras)
            trial[i] = cand
            c = measure("\n\n".join(trial))
            if c > best_cv:
                best_cv, best_i, best_p = c, i, cand
        if best_i is None:
            break                      # no productive edit anywhere
        paras[best_i] = best_p
        passes += 1

    out_text = "\n\n".join(paras)
    paras_out = tok.paragraphs(out_text)
    cv1 = measure(out_text)
    # INVARIANT: paragraph count must be unchanged
    if len(paras_out) != len(paras_in):
        return MicroResult(text, cv0, cv0, cv_min, 0, len(paras_in), len(paras_in),
                           measure(text) >= cv_min,
                           "aborted: paragraph count would change — returned input unchanged")
    return MicroResult(out_text, round(cv0, 4), round(cv1, 4), cv_min, passes,
                       len(paras_in), len(paras_out), cv1 >= cv_min,
                       "ok" if cv1 >= cv_min else f"CV {cv1:.2f} still under {cv_min} after {passes} passes")
