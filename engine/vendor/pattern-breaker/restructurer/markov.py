"""
Markov text-extension engine (Phase 2 helper).

Purpose
-------
Provide *rhythm-breaking raw material* — short, on-topic word runs and cadence
seeds — that Claude is instructed to weave in when restructuring a flagged span.
It exists to inject controlled irregularity (variable sentence starts, connective
variety, burst length) WITHOUT inventing facts.

No-hallucination guarantees
---------------------------
1. The chain is trained ONLY on:
     - the flagged span's own tokens (primary), and
     - dictionary/human_corpus.json — 2,307 real human travel forum sentences
       pulled from the voyagerscontent/human-dictionary-travel repo (reference).
   No open-web text, no model-generated text, no outside facts.
2. Output is capped to short fragments (default <= 6 words) and is delivered to
   Claude as *suggested cadence seeds / connective options*, never as asserted
   content. The Phase 2 fact-safety guard still rejects any span that introduces
   a NEW named entity or number relative to the original — so even if a Markov
   fragment surfaced a corpus word, it cannot survive into output as a new fact.
3. Determinism is controlled: given the same span text + same seed, the same
   fragments are produced (seeded PRNG). Different spans get different seeds, so
   the whole document is NON-PATTERNED but still reproducible for auditing.

This mirrors the seeded Markov picker already used in human-dictionary-travel's
engine.py — deterministic yet non-repetitive.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_WORD = re.compile(r"[A-Za-z0-9']+")
CORPUS_PATH = Path(__file__).resolve().parent.parent / "dictionary" / "human_corpus.json"


def _seed_from(text: str, salt: str = "") -> int:
    h = hashlib.sha256((salt + "::" + text).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


class MarkovExtender:
    """First- and second-order word Markov chain over a constrained vocabulary."""

    def __init__(
        self,
        span_text: str,
        use_corpus: bool = True,
        corpus_bucket_keywords: Optional[List[str]] = None,
        corpus_path: Optional[str] = None,
        order: int = 2,
        max_corpus_sentences: int = 400,
    ):
        self.order = max(1, min(order, 2))
        self.span_text = span_text
        self.chain: Dict[Tuple[str, ...], List[str]] = defaultdict(list)
        self.starts: List[Tuple[str, ...]] = []
        self.vocab: set = set()

        # 1) train on the span itself (primary, weighted by inclusion twice)
        self._train(span_text)
        self._train(span_text)

        # 2) train on relevant human corpus sentences (reference variety only)
        if use_corpus:
            self._train_corpus(corpus_path, corpus_bucket_keywords, max_corpus_sentences)

    # -- training -------------------------------------------------------------
    def _train(self, text: str) -> None:
        for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
            toks = _WORD.findall(sent)
            if len(toks) < self.order + 1:
                continue
            self.vocab.update(w.lower() for w in toks)
            padded = toks
            self.starts.append(tuple(w for w in padded[: self.order]))
            for i in range(len(padded) - self.order):
                key = tuple(padded[i : i + self.order])
                nxt = padded[i + self.order]
                self.chain[key].append(nxt)

    def _train_corpus(
        self,
        corpus_path: Optional[str],
        bucket_keywords: Optional[List[str]],
        limit: int,
    ) -> None:
        p = Path(corpus_path) if corpus_path else CORPUS_PATH
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return
        phrases = data.get("phrases", [])
        selected = []
        if bucket_keywords:
            kw = {k.lower() for k in bucket_keywords}
            for ph in phrases:
                buckets = {b.lower() for b in ph.get("buckets", [])}
                if buckets & kw:
                    selected.append(ph["phrase"])
        if not selected:
            selected = [ph["phrase"] for ph in phrases]
        for phrase in selected[:limit]:
            self._train(phrase)

    # -- generation -----------------------------------------------------------
    def cadence_seeds(
        self,
        n: int = 5,
        max_len: int = 6,
        min_len: int = 2,
        seed_salt: str = "",
    ) -> List[str]:
        """
        Return up to n short fragments of varying length (min_len..max_len words).
        Lengths are drawn from a seeded PRNG so the SET of fragments is bursty
        (mixed short/long) yet reproducible for a given span+salt.
        """
        if not self.chain or not self.starts:
            return []
        rng = random.Random(_seed_from(self.span_text, seed_salt))
        out: List[str] = []
        attempts = 0
        seen = set()
        while len(out) < n and attempts < n * 8:
            attempts += 1
            target = rng.randint(min_len, max_len)   # varied length => burstiness
            key = rng.choice(self.starts)
            words = list(key)
            cur = key
            while len(words) < target:
                choices = self.chain.get(cur)
                if not choices:
                    break
                nxt = choices[rng.randrange(len(choices))]
                words.append(nxt)
                cur = tuple(words[-self.order :])
            frag = " ".join(words).strip()
            low = frag.lower()
            if min_len <= len(words) and low not in seen and frag:
                seen.add(low)
                out.append(frag)
        return out

    def paragraph_shape(self, seed_salt: str = "") -> Dict[str, int]:
        """
        Suggest a randomized-but-reproducible paragraph/sentence shape to break
        uniform structure: number of paragraphs and a per-paragraph sentence
        count list. Claude is told to APPROXIMATE this shape, not pad with filler.
        """
        rng = random.Random(_seed_from(self.span_text, "shape:" + seed_salt))
        n_para = rng.randint(1, 3)
        shape = [rng.randint(1, 5) for _ in range(n_para)]
        return {"paragraphs": n_para, "sentences_per_paragraph": shape}


if __name__ == "__main__":
    import sys
    txt = sys.stdin.read() if not sys.argv[1:] else Path(sys.argv[1]).read_text()
    m = MarkovExtender(txt, corpus_bucket_keywords=["galapagos", "cruise", "general"])
    print("cadence seeds:", json.dumps(m.cadence_seeds(), indent=2))
    print("paragraph shape:", json.dumps(m.paragraph_shape()))
