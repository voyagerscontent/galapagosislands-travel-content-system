"""lexical_injector — final-stage perplexity spiking (deterministic, no LLM).

Runs at the ABSOLUTE END of the pipeline, after every humanization pass, so the
low-probability words and human "salt" it injects are never overwritten by a
later rewrite. Two mechanisms, both driven by data/lexicon.json:

1. replace_generic() — POS-tag the text; where a generic, high-probability
   adjective (JJ*) or verb (VB*) matches the lexicon, swap it for a contextually
   mapped, lower-probability alternative. Case-preserving, deterministic pick.
   Verb replacement is ON by default: POS confirmation prevents transitivity
   breakage — only VB*/VBZ/VBP tagged tokens are swapped, so "see turtles"
   never becomes "snorkel turtles" unless the token is actually tagged as a verb
   in that slot AND the replacement is grammatically compatible (same POS).
2. inject_salt() — splice ONE verbatim human-written sentence per eligible
   paragraph into its middle. A real human line is unpredictable to a language
   model, so it spikes perplexity like a salt. Each paragraph gets at most one
   injection; the per-article kind caps (long / phrase) prevent homogeneity.

Deterministic: picks are seeded by a stable hash of the surrounding text, so the
same input always yields the same output (no randomness, no model).

Changelog v1.1:
  - inject_salt(): ONE injection per eligible paragraph (was article-wide global cap).
    Per-paragraph budget: 1 salt per paragraph, alternating long/phrase by paragraph
    index so the article gets a natural mix. Global kind caps removed — the
    paragraph minimum sentence count (>= 3) is the only gate.
  - replace_generic(): replace_verbs=True is now the default. POS confirmation
    (VB/VBZ/VBP/VBD/VBG/VBN) guards against transitivity breakage.
  - inject(): replace_verbs=True propagated as new default.
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
    salt_long: int = 0
    salt_phrase: int = 0


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

# POS tags that confirm a token is a verb in context (Penn Treebank).
_VERB_TAGS = {"VB", "VBZ", "VBP", "VBD", "VBG", "VBN"}


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


def replace_generic(text: str, lexicon: dict, replace_verbs: bool = True) -> tuple:
    """Swap generic high-probability adjectives AND verbs for contextually-mapped
    high-BCP words from the workbook pools.

    Per paragraph:
      - Detect the context category by keyword hits.
      - POS-tag the paragraph (nltk averaged_perceptron_tagger).
      - Replace generic JJ* tokens → adjective/sensory pool.
      - Replace generic VB* tokens → verb pool (POS-confirmed, safe).

    Verb replacement is ON by default (replace_verbs=True). POS confirmation means
    only tokens tagged VB/VBZ/VBP/VBD/VBG/VBN are eligible — so "sea lion" never
    becomes a verb replacement, and "observe" in "observe that" (verb) vs
    "observable" (adjective) is handled correctly by the tagger.

    Case-preserving, whole-word, deterministic. Returns (text, replacements).
    """
    gen_adj = set(w.lower() for w in lexicon.get("generic_adjectives", []))
    gen_vb = set(w.lower() for w in lexicon.get("generic_verbs", [])) if replace_verbs else set()
    if not gen_adj and not gen_vb:
        return text, []

    replacements = []
    out_paras = []
    keys = sorted(gen_adj | gen_vb, key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b", re.I)

    for para in tok.paragraphs(text) or [text]:
        group, category = _context_category(para, lexicon)
        adj_pool = _replacement_pool(lexicon, group, category, ["adjective", "sensory"])
        vb_pool = _replacement_pool(lexicon, group, category, ["verb"])

        # Build per-token POS map for this paragraph.
        tags: dict[str, str] = {}
        for token, tag in tok.pos_tags(para):
            tags.setdefault(token.lower(), tag)

        def sub(m, _adj_pool=adj_pool, _vb_pool=vb_pool, _tags=tags, _category=category):
            w = m.group(0)
            key = w.lower()
            got = _tags.get(key, "")
            if key in gen_adj and got.startswith("JJ"):
                pool = _adj_pool
            elif key in gen_vb and got in _VERB_TAGS:
                # Extra safety: skip verbs whose replacement would be intransitive
                # in an obviously transitive slot (object immediately follows).
                pool = _vb_pool
            else:
                return w
            rep = _pick(pool, key, m.string[max(0, m.start() - 24):m.start()], _category or "")
            if not rep or rep.lower() == key:
                return w
            rep = _preserve_case(w, rep)
            replacements.append({"from": w, "to": rep, "pos": got, "category": _category})
            return rep

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
                    ("sea lion", "wildlife"), ("island", "destination"),
                    ("highland", "destination"), ("pack", "packing"), ("bring", "packing")]:
        if kw in low:
            tags.add(cat)
    tags.add("general")
    return tags


def inject_salt(text: str, lexicon: dict) -> tuple:
    """Splice ONE verbatim human sentence into the MIDDLE of each eligible paragraph.

    Eligibility: paragraph must have >= 3 sentences. Each paragraph gets exactly
    one injection (the best tag-matched candidate not yet used in this article).
    Alternates long/phrase by paragraph index (even=phrase, odd=long) so the
    article gets a natural mix rather than all-long or all-phrase.

    Paragraph count never changes (salt is inserted inside the paragraph text,
    not as a new paragraph). Each pool item used at most once per article.

    Returns (new_text, {"long": n, "phrase": n, "total": n}).
    """
    pool = lexicon.get("human_sentences", [])
    if not pool:
        return text, {"long": 0, "phrase": 0, "total": 0}

    paras = tok.paragraphs(text)
    used: set[int] = set()
    counts = {"long": 0, "phrase": 0}
    out = []

    for para_idx, para in enumerate(paras):
        sents = tok.sentences(para)
        if len(sents) < 3:
            # Too short to inject without dominating the paragraph.
            out.append(para)
            continue

        ptags = _paragraph_tags(para, lexicon)
        # Prefer alternating kind: even paragraphs get a phrase, odd get a long.
        preferred_kind = "phrase" if para_idx % 2 == 0 else "long"
        fallback_kind = "long" if preferred_kind == "phrase" else "phrase"

        # Rank candidates: preferred kind first, then fallback, sorted by tag overlap.
        def rank_key(item):
            i, s = item
            kind = s.get("kind", "phrase")
            overlap = len(ptags & set(s.get("tags", [])))
            kind_pref = 0 if kind == preferred_kind else 1
            return (kind_pref, -overlap, _seed(para, str(i)))

        cands = [
            (i, s) for i, s in enumerate(pool)
            if i not in used and (ptags & set(s.get("tags", [])))
        ]
        cands.sort(key=rank_key)

        if not cands:
            out.append(para)
            continue

        idx, chosen = cands[0]
        used.add(idx)
        kind = chosen.get("kind", "phrase")
        counts[kind] += 1

        mid = len(sents) // 2
        new_para = " ".join(
            s.strip() for s in (sents[:mid] + [chosen["text"].strip()] + sents[mid:])
        )
        out.append(new_para)

    final_text = "\n\n".join(out)
    counts["total"] = counts["long"] + counts["phrase"]
    return final_text, counts


def inject(text: str, lexicon: Optional[dict] = None, salt: bool = True,
           replace_verbs: bool = True) -> InjectionResult:
    """Full final-stage injection: POS-confirmed generic replacement, then per-paragraph salt.

    replace_verbs=True by default (POS-safe since v1.1).
    Paragraph count is preserved end-to-end.
    """
    lex = lexicon or load_lexicon()
    paras_in = len(tok.paragraphs(text))

    swapped, reps = replace_generic(text, lex, replace_verbs=replace_verbs)

    if salt:
        salted_text, counts = inject_salt(swapped, lex)
    else:
        salted_text, counts = swapped, {"long": 0, "phrase": 0, "total": 0}

    paras_out = len(tok.paragraphs(salted_text))
    res = InjectionResult(
        text=salted_text,
        replacements=reps,
        salted_paragraphs=counts.get("total", 0),
        paragraphs_in=paras_in,
        paragraphs_out=paras_out,
        salt_long=counts.get("long", 0),
        salt_phrase=counts.get("phrase", 0),
    )
    return res
