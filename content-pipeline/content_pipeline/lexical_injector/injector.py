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


def _context_category(paragraph: str, lexicon: dict) -> tuple:
    """Best (group, category) match for a paragraph, by counting how many of each
    category's distinctive words (nouns/places) appear. Returns (None, None) if
    nothing matches — the caller then uses a general feeling pool."""
    low = paragraph.lower()
    best, best_hits = (None, None), 0
    for group, cats in lexicon.get("pools", {}).items():
        for cat, buckets in cats.items():
            hits = 0
            for w in buckets.get("noun", []) + buckets.get("place", []):
                if len(w) >= 5 and w.lower() in low:
                    hits += 1
            if hits > best_hits:
                best_hits, best = hits, (group, cat)
    return best


# A clean drop-in replacement is a single lowercase alphabetic word (no hyphenated
# compounds, place names, or the workbook's occasional POS mislabels like "dry-dock").
_CLEAN = re.compile(r"^[a-z]{4,}$")


def _clean_pool(words: list) -> list:
    return [w for w in words if _CLEAN.match(w)]


def _replacement_pool(lexicon: dict, group, category, buckets: list) -> list:
    """Clean words of the requested POS buckets for a (group, category), with
    fallbacks: the category → its whole group → the feeling group (universal)."""
    pools = lexicon.get("pools", {})
    def collect(scope_cats):
        out = []
        for cat in scope_cats:
            for b in buckets:
                out += cat.get(b, [])
        return _clean_pool(out)
    if group and category:
        got = collect([pools.get(group, {}).get(category, {})])
        if got:
            return got
    if group:
        got = collect(list(pools.get(group, {}).values()))
        if got:
            return got
    return collect(list(pools.get("feeling", {}).values()))


def replace_generic(text: str, lexicon: dict, replace_verbs: bool = False) -> tuple:
    """Swap generic high-probability adjectives (and optionally verbs) for
    contextually-mapped high-BCP words from the workbook pools. Per paragraph:
    detect the context category, then replace generic JJ -> adjective/sensory
    pool. Verb replacement is OFF by default: arbitrary domain verbs break
    transitivity ("see turtles" -> "snorkel turtles"); enable with care.
    POS-confirmed, whole-word, case-preserving. Returns (text, replacements)."""
    gen_adj = set(w.lower() for w in lexicon.get("generic_adjectives", []))
    gen_vb = set(w.lower() for w in lexicon.get("generic_verbs", [])) if replace_verbs else set()
    if not gen_adj and not gen_vb:
        return text, []
    replacements = []
    out_paras = []
    for para in tok.paragraphs(text) or [text]:
        group, category = _context_category(para, lexicon)
        adj_pool = _replacement_pool(lexicon, group, category, ["adjective", "sensory"])
        vb_pool = _replacement_pool(lexicon, group, category, ["verb"])
        tags = {}
        for token, tag in tok.pos_tags(para):
            tags.setdefault(token.lower(), tag)

        def sub(m):
            w = m.group(0)
            key = w.lower()
            got = tags.get(key, "")
            if key in gen_adj and got.startswith("JJ"):
                pool = adj_pool
            elif key in gen_vb and got.startswith("VB"):
                pool = vb_pool
            else:
                return w
            rep = _pick(pool, key, m.string[max(0, m.start() - 24):m.start()], category or "")
            if not rep or rep.lower() == key:
                return w
            rep = _preserve_case(w, rep)
            replacements.append({"from": w, "to": rep, "category": category})
            return rep

        keys = sorted(gen_adj | gen_vb, key=len, reverse=True)
        pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b", re.I)
        out_paras.append(pattern.sub(sub, para))
    return "\n\n".join(out_paras), replacements


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


def inject_salt(text: str, lexicon: dict, max_long: int = 2, max_phrase: int = 3) -> tuple:
    """Splice tag-matched verbatim human sentences into paragraph MIDDLES, with
    SEPARATE caps per kind: up to `max_long` long sentences + up to `max_phrase`
    short phrases per article. Each line used once; paragraph count never changes.
    Returns (new_text, {"long": n, "phrase": n})."""
    pool = lexicon.get("human_sentences", [])
    if not pool:
        return text, {"long": 0, "phrase": 0}
    caps = {"long": max_long, "phrase": max_phrase}
    done = {"long": 0, "phrase": 0}
    paras = tok.paragraphs(text)
    used = set()
    out = []
    for para in paras:
        sents = tok.sentences(para)
        if len(sents) < 3 or sum(done.values()) >= sum(caps.values()):
            out.append(para)
            continue
        ptags = _paragraph_tags(para, lexicon)
        # candidates whose kind still has budget, ranked by tag overlap
        cands = [(i, s) for i, s in enumerate(pool)
                 if i not in used and done[s.get("kind", "phrase")] < caps[s.get("kind", "phrase")]]
        cands.sort(key=lambda t: (-len(ptags & set(t[1].get("tags", []))), _seed(para, str(t[0]))))
        cands = [c for c in cands if ptags & set(c[1].get("tags", []))]
        if not cands:
            out.append(para)
            continue
        idx, chosen = cands[0]
        used.add(idx)
        done[chosen.get("kind", "phrase")] += 1
        mid = len(sents) // 2
        out.append(" ".join(s.strip() for s in (sents[:mid] + [chosen["text"].strip()] + sents[mid:])))
    return "\n\n".join(out), done


def inject(text: str, lexicon: Optional[dict] = None, salt: bool = True,
           replace_verbs: bool = False, max_salted: Optional[int] = None) -> InjectionResult:
    """Full final-stage injection: replace generics, then salt. Paragraph-preserving."""
    lex = lexicon or load_lexicon()
    paras = tok.paragraphs(text)
    paras_in = len(paras)
    swapped, reps = replace_generic(text, lex, replace_verbs=replace_verbs)
    if salt:
        salted_text, counts = inject_salt(swapped, lex, max_long=2, max_phrase=3)
    else:
        salted_text, counts = swapped, {"long": 0, "phrase": 0}
    res = InjectionResult(salted_text, reps, counts["long"] + counts["phrase"],
                          paras_in, len(tok.paragraphs(salted_text)))
    res.salt_long, res.salt_phrase = counts["long"], counts["phrase"]
    return res
