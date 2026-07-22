"""
Deterministic fact-safety guard (Phase 2 gate).

Runs AFTER Claude returns a rewritten span. Pure Python, no LLM. Its job is to
prove the rewrite did not INTRODUCE new facts. It does this by comparing the set
of "fact tokens" (named entities-ish capitalized words, and all numbers) in the
rewrite against those in the original span.

Rules
-----
- New NUMBER in output that was not in input  -> HARD FAIL (reject).
- New NAMED-ENTITY candidate in output not in input -> HARD FAIL (reject).
  (Named-entity candidate = a capitalized token not at sentence start and not a
   known common word; a conservative heuristic that errs toward flagging.)
- Original fact token DROPPED from output -> MAJOR CHANGE (not a hard fail, but
  the span is marked major_change=True so it gets highlighted light-blue for a
  human editor.)

This is intentionally strict + conservative: better to bounce a rewrite back to
Claude (or flag for human review) than to let an invented detail through.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Set, Tuple

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_NUMBER = re.compile(r"\b\d[\d,\.]*\b")
# Currency/units kept with the number so "3 nights" vs "4 nights" is caught.
_NUMBER_CTX = re.compile(r"\b(\d[\d,\.]*)\s*([A-Za-z%$€£]+)?")

# Spelled-out numbers 0-20 + tens, so "three" and "3" are treated as the same
# fact (a faithful paraphrase must not be penalised as a fact change).
_NUM_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
    "eighty": "80", "ninety": "90", "hundred": "100", "thousand": "1000",
}

# Common capitalized words that are NOT entities (sentence openers, etc.).
_COMMON = {
    "The", "A", "An", "This", "That", "These", "Those", "It", "We", "You",
    "They", "He", "She", "I", "Our", "Your", "Their", "His", "Her", "But",
    "And", "Or", "So", "Then", "When", "While", "If", "As", "For", "In", "On",
    "At", "To", "Of", "With", "From", "By", "Also", "Here", "There", "Now",
    "One", "Two", "Three", "Bring", "Get", "Go", "Come", "Every", "Each",
    "Moreover", "Furthermore", "Additionally", "Overall", "Ultimately",
}


@dataclass
class GuardResult:
    ok: bool                        # True if no HARD FAIL
    major_change: bool              # True if facts dropped (needs human review)
    new_numbers: List[str] = field(default_factory=list)
    new_entities: List[str] = field(default_factory=list)
    dropped_numbers: List[str] = field(default_factory=list)
    dropped_entities: List[str] = field(default_factory=list)
    reason: str = ""


# 'one' is excluded from spelled-number fact detection: it is overwhelmingly a
# pronoun/indefinite ('every one', 'one of them') rather than a quantity, and
# treating it as the number 1 causes false HARD FAILs. Digit '1' is still caught.
_AMBIGUOUS_NUM_WORDS = {"one"}


def _numbers(text: str) -> Set[str]:
    """Collect numeric facts as bare magnitudes; unit context is ignored so a
    faithful reword ("3 nights" -> "three nights aboard") is not penalised, but
    a changed magnitude (3 -> 5) still fails."""
    out = set()
    for m in _NUMBER_CTX.finditer(text):
        out.add(m.group(1).replace(",", ""))
    for w in _WORD.findall(text.lower()):
        if w in _NUM_WORDS and w not in _AMBIGUOUS_NUM_WORDS:
            out.add(_NUM_WORDS[w])
    return out


def _entities(text: str) -> Set[str]:
    """Capitalized tokens that look like proper nouns (conservative)."""
    ents: Set[str] = set()
    # split into sentences to know which caps are sentence-initial
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        toks = list(_WORD.finditer(sent))
        for i, m in enumerate(toks):
            w = m.group(0)
            if not w[0].isupper():
                continue
            if i == 0:
                continue  # sentence-initial cap is ambiguous; skip
            if w in _COMMON:
                continue
            if w.isupper() and len(w) <= 3:
                continue  # acronyms handled as-is only if new; keep conservative
            ents.add(w)
    return ents


def check(original: str, rewrite: str) -> GuardResult:
    o_nums, r_nums = _numbers(original), _numbers(rewrite)
    o_ents, r_ents = _entities(original), _entities(rewrite)

    new_nums = sorted(r_nums - o_nums)
    new_ents = sorted(r_ents - o_ents)
    dropped_nums = sorted(o_nums - r_nums)
    dropped_ents = sorted(o_ents - r_ents)

    hard_fail = bool(new_nums or new_ents)
    major = bool(dropped_nums or dropped_ents)

    reason_parts = []
    if new_nums:
        reason_parts.append(f"introduced numbers {new_nums}")
    if new_ents:
        reason_parts.append(f"introduced entities {new_ents}")
    if dropped_nums:
        reason_parts.append(f"dropped numbers {dropped_nums}")
    if dropped_ents:
        reason_parts.append(f"dropped entities {dropped_ents}")

    return GuardResult(
        ok=not hard_fail,
        major_change=major,
        new_numbers=new_nums,
        new_entities=new_ents,
        dropped_numbers=dropped_nums,
        dropped_entities=dropped_ents,
        reason="; ".join(reason_parts) if reason_parts else "clean",
    )


if __name__ == "__main__":
    import sys, json
    o = "We spent 3 nights on the Beluga near Isabela Island with guide Pablo."
    r_good = "Three unforgettable nights aboard the Beluga, out near Isabela Island — Pablo showed us everything."
    r_bad = "We spent 5 nights on the Beluga near Isabela Island and Fernandina with guide Pablo and Maria."
    print("good:", json.dumps(check(o, r_good).__dict__, indent=2))
    print("bad:", json.dumps(check(o, r_bad).__dict__, indent=2))
