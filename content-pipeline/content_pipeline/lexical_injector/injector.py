"""lexical_injector — final-stage perplexity spiking (deterministic, no LLM).

Runs at the ABSOLUTE END of the pipeline, after every humanization pass, so the
low-probability words and human "salt" it injects are never overwritten by a
later rewrite. Two mechanisms, both driven by data/lexicon.json:

1. replace_generic() — POS-tag the text; where a generic, high-probability
   adjective (JJ*) or verb (VB*) matches the lexicon, swap it for a contextually
   mapped, lower-probability alternative. Case-preserving, deterministic pick.
2. inject_salt() — splice a VERBATIM human-written sentence (tag-matched to the
   paragraph) into the MIDDLE of an AI paragraph. A real human line is
   unpredictable to a language model, so it spikes perplexity like a salt.

Deterministic: picks are seeded by a stable hash of the surrounding text, so the
same input always yields the same output (no randomness, no model).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from content_pipeline.common import tokenizer as tok

_DEFAULT_LEXICON = os.path.join(os.path.dirname(__file__), "..", "..", "data", "lexicon.json")


def load_lexicon(path: str = _DEFAULT_LEXICON) -> dict:
    """JSON loader for the high-BCP database (destination / activity / feeling)."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _seed(*parts: str) -> int:
    h = hashlib.blake2b(digest_size=8)
    for p in parts:
        h.update(p.encode("utf-8", "replace"))
        h.update(b"\x1f")
    return int.from_bytes(h.digest(), "big")


def _pick(options: List[str], *ctx: str) -> str:
    return options[_seed(*ctx) % len(options)] if options else ""


def _preserve_case(src: str, rep: str) -> str:
    if src[:1].isupper():
        return rep[:1].upper() + rep[1:]
    return rep


@dataclass
class InjectionResult:
    text: str
    replacements: List[dict] = field(default_factory=list)
    salted_paragraphs: int = 0
    paragraphs_in: int = 0
    paragraphs_out: int = 0


def replace_generic(text: str, lexicon: dict) -> tuple:
    """Swap generic high-probability JJ/VB tokens for mapped low-probability ones.

    Returns (new_text, replacements). Only whole-word, POS-confirmed matches are
    touched; everything else is left byte-for-byte."""
    rules = {k.lower(): v for k, v in lexicon.get("generic_replacements", {}).items()}
    if not rules:
        return text, []
    replacements = []
    # POS-tag once; then do targeted, boundary-safe substitutions on the raw text.
    tags = dict()
    for token, tag in tok.pos_tags(text):
        tags.setdefault(token.lower(), tag)

    def sub(m):
        w = m.group(0)
        key = w.lower()
        rule = rules.get(key)
        if not rule:
            return w
        want = rule.get("pos", "")[:2]           # JJ or VB family
        got = tags.get(key, "")
        if want and not got.startswith(want):
            return w                              # POS doesn't match -> skip
        rep = _pick(rule.get("options", []), key, m.string[max(0, m.start() - 24):m.start()])
        if not rep:
            return w
        rep = _preserve_case(w, rep)
        replacements.append({"from": w, "to": rep, "category": rule.get("category")})
        return rep

    keys = sorted(rules, key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b", re.I)
    new_text = pattern.sub(sub, text)
    return new_text, replacements


def _paragraph_tags(paragraph: str, lexicon: dict) -> set:
    """Rough contextual tags for a paragraph from category vocabulary hits."""
    low = paragraph.lower()
    tags = set()
    for cat, words in lexicon.get("categories", {}).items():
        if any(w.split()[-1] in low for w in words):
            tags.add(cat)
    for kw, cat in [("snorkel", "snorkel"), ("dive", "snorkel"), ("panga", "cruise"),
                    ("cruise", "cruise"), ("wildlife", "wildlife"), ("bird", "wildlife"),
                    ("sea lion", "wildlife"), ("pack", "packing"), ("bring", "packing")]:
        if kw in low:
            tags.add(cat)
    tags.add("general")
    return tags


def inject_salt(text: str, lexicon: dict, max_salted: Optional[int] = None) -> tuple:
    """Splice a tag-matched verbatim human sentence into the MIDDLE of paragraphs.

    One salt per eligible paragraph (>= 3 sentences so there is a real middle),
    each human line used at most once. Returns (new_text, count). Paragraph count
    is never changed — the sentence goes *inside* an existing paragraph."""
    pool = lexicon.get("human_sentences", [])
    if not pool:
        return text, 0
    paras = tok.paragraphs(text)
    used = set()
    salted = 0
    out = []
    for pi, para in enumerate(paras):
        sents = tok.sentences(para)
        if len(sents) < 3 or (max_salted is not None and salted >= max_salted):
            out.append(para)
            continue
        ptags = _paragraph_tags(para, lexicon)
        # best unused human sentence by tag overlap, deterministic tie-break
        cands = [(i, s) for i, s in enumerate(pool) if i not in used]
        cands.sort(key=lambda t: (-len(ptags & set(t[1].get("tags", []))),
                                  _seed(para, str(t[0]))))
        if not cands or not (ptags & set(cands[0][1].get("tags", []))):
            out.append(para)
            continue
        idx, chosen = cands[0]
        used.add(idx)
        mid = len(sents) // 2                      # insert into the middle
        new_sents = sents[:mid] + [chosen["text"].strip()] + sents[mid:]
        out.append(" ".join(s.strip() for s in new_sents))
        salted += 1
    return "\n\n".join(out), salted


def inject(text: str, lexicon: Optional[dict] = None, salt: bool = True,
           max_salted: Optional[int] = None) -> InjectionResult:
    """Full final-stage injection: replace generics, then salt. Paragraph-preserving."""
    lex = lexicon or load_lexicon()
    paras_in = len(tok.paragraphs(text))
    swapped, reps = replace_generic(text, lex)
    salted_text, n_salt = (inject_salt(swapped, lex, max_salted) if salt else (swapped, 0))
    return InjectionResult(salted_text, reps, n_salt, paras_in, len(tok.paragraphs(salted_text)))
