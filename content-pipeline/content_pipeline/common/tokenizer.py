"""Shared tokenizer/POS interface — the ONE place NLP backend is chosen.

Modules never import nltk/spaCy directly; they call these functions. That keeps
micro_guardrail and lexical_injector decoupled from the backend, so spaCy can
replace nltk in production by editing only this file. Default backend is nltk
(pure-Python, installs everywhere; spaCy has no wheels on Python 3.14 yet).
"""
from __future__ import annotations

import functools
import re
from typing import List, Tuple

_PARA_SPLIT = re.compile(r"\n\s*\n+")


@functools.lru_cache(maxsize=1)
def _nltk():
    import nltk
    for pkg, path in [("punkt", "tokenizers/punkt"),
                      ("punkt_tab", "tokenizers/punkt_tab"),
                      ("averaged_perceptron_tagger", "taggers/averaged_perceptron_tagger"),
                      ("averaged_perceptron_tagger_eng", "taggers/averaged_perceptron_tagger_eng")]:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(pkg, quiet=True)
    return nltk


def paragraphs(text: str) -> List[str]:
    """Split into paragraphs on blank lines — the structural unit macro/micro
    must preserve. Returns the raw paragraph strings (blank ones dropped)."""
    return [p for p in _PARA_SPLIT.split(text.strip()) if p.strip()]


def sentences(text: str) -> List[str]:
    return [s for s in _nltk().sent_tokenize(text) if s.strip()]


def words(text: str) -> List[str]:
    """Word tokens that carry length signal (punctuation-only tokens dropped)."""
    return [w for w in _nltk().word_tokenize(text) if re.search(r"\w", w)]


def word_count(sentence: str) -> int:
    return len(words(sentence))


def pos_tags(text: str) -> List[Tuple[str, str]]:
    """(token, POS) pairs. Penn Treebank tags (JJ* adjectives, VB* verbs, …)."""
    n = _nltk()
    return n.pos_tag(n.word_tokenize(text))
