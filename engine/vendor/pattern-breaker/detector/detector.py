"""
Phase 1 — Deterministic pattern detector.

Pure Python. No LLM. No network. No randomness. No learned weights.

Everything below is arithmetic on token/sentence/paragraph statistics compared
against the fixed thresholds in config/thresholds.json. The same text + the
same thresholds file always yields the exact same flags. This is the guarantee
that "no hallucination enters the system": Phase 1 never asks a model anything.

Detected factors (each maps 1:1 to a user requirement):
  1. ngram_formula        -> "a pattern or formula within text" / "repetitive formulas"
  2. sentence_rhythm      -> "a repetitive rhythm in text"
  3. burstiness           -> "lack of burstiness"
  4. sentence_structure   -> "a pattern in sentences"
  5. paragraph_pattern    -> "a pattern in paragraphs"
  6. transition_formula   -> formulaic connectives (supports 1 & 6)

Output: a DetectionReport listing, per factor, whether it fired, the numeric
metric that caused it, the threshold it breached, and the exact character spans
(offsets into the original text) that should be handed to Phase 2 — nothing else.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "thresholds.json"

# --- Deterministic tokenizers -------------------------------------------------
# Sentence splitter: split on ., !, ? followed by whitespace. Deterministic and
# dependency-free (no nltk). Handles common abbreviations minimally to avoid
# over-splitting; we favor reproducibility over linguistic perfection.
_ABBREV = {"mr", "mrs", "ms", "dr", "st", "vs", "etc", "e.g", "i.e", "u.s", "u.k"}
_SENT_END = re.compile(r'([.!?]+)(\s+|$)')
_WORD = re.compile(r"[A-Za-z0-9']+")
_PARA_SPLIT = re.compile(r'\n\s*\n')

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "it", "its", "this", "that", "these", "those", "you", "your", "we", "our",
    "they", "their", "he", "she", "his", "her", "i", "me", "my",
}


def _load_config(path: Optional[str] = None) -> dict:
    p = Path(path) if path else CONFIG_PATH
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class Sentence:
    text: str
    start: int          # char offset into original text
    end: int
    para_index: int
    word_count: int
    first_token: str
    opening_bigram: str


@dataclass
class Flag:
    factor: str                 # which detector fired
    reason: str                 # human-readable explanation
    metric: float               # computed value
    threshold: float            # threshold breached
    scope: str                  # document | paragraph | sentence | span
    span_start: int             # char offset (document flags use full-doc span)
    span_end: int
    span_text: str


@dataclass
class DetectionReport:
    flagged: bool
    word_count: int
    sentence_count: int
    paragraph_count: int
    metrics: Dict[str, float] = field(default_factory=dict)
    flags: List[Flag] = field(default_factory=list)
    flagged_spans: List[Dict] = field(default_factory=list)  # dedup spans -> Phase 2
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# --- Text structure parsing (deterministic) -----------------------------------
def _split_sentences_with_offsets(text: str) -> List[Tuple[str, int, int]]:
    """Return list of (sentence_text, start_offset, end_offset)."""
    out: List[Tuple[str, int, int]] = []
    idx = 0
    n = len(text)
    start = 0
    for m in _SENT_END.finditer(text):
        end = m.end(1)  # include the punctuation
        chunk = text[start:end]
        # guard against splitting on abbreviations like "e.g."
        tail = _WORD.findall(chunk[-6:].lower())
        stripped = chunk.strip()
        if stripped:
            last = tail[-1] if tail else ""
            if last in _ABBREV and end < n:
                continue  # keep accumulating
            # locate true start ignoring leading whitespace
            real_start = start + (len(chunk) - len(chunk.lstrip()))
            out.append((text[real_start:end].strip(), real_start, end))
        start = m.end()
    # trailing text without terminal punctuation
    if start < n and text[start:].strip():
        real_start = start + (len(text[start:]) - len(text[start:].lstrip()))
        out.append((text[real_start:].strip(), real_start, n))
    return out


def _parse(text: str) -> List[Sentence]:
    sentences: List[Sentence] = []
    # paragraph offsets
    para_bounds: List[Tuple[int, int]] = []
    pos = 0
    for part in _PARA_SPLIT.split(text):
        start = text.find(part, pos)
        end = start + len(part)
        para_bounds.append((start, end))
        pos = end

    def para_of(offset: int) -> int:
        for i, (s, e) in enumerate(para_bounds):
            if s <= offset < e:
                return i
        return len(para_bounds) - 1

    for stext, s0, s1 in _split_sentences_with_offsets(text):
        words = _WORD.findall(stext.lower())
        if not words:
            continue
        first = words[0]
        bigram = " ".join(words[:2]) if len(words) >= 2 else first
        sentences.append(Sentence(
            text=stext, start=s0, end=s1, para_index=para_of(s0),
            word_count=len(words), first_token=first, opening_bigram=bigram,
        ))
    return sentences


# --- Math helpers --------------------------------------------------------------
def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _variance(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def _std(xs: List[float]) -> float:
    return math.sqrt(_variance(xs))


def _cv(xs: List[float]) -> float:
    """Coefficient of variation = std / mean. Low CV => uniform => mechanical."""
    m = _mean(xs)
    if m == 0:
        return 0.0
    return _std(xs) / m


def _autocorr_lag1(xs: List[float]) -> float:
    """Lag-1 autocorrelation of a series. High value => predictable rhythm."""
    n = len(xs)
    if n < 3:
        return 0.0
    m = _mean(xs)
    denom = sum((x - m) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    num = sum((xs[i] - m) * (xs[i + 1] - m) for i in range(n - 1))
    return num / denom


def _burstiness(xs: List[float]) -> float:
    """
    Burstiness B = (sigma - mu) / (sigma + mu), Goh & Barabasi (2008),
    remapped to [0,1] where 0 = perfectly regular (Poisson-like/uniform) and
    1 = highly bursty. Human prose scores higher; AI prose clusters low.
    We use the normalized coefficient-of-variation form and clamp.
    """
    mu = _mean(xs)
    sigma = _std(xs)
    if (sigma + mu) == 0:
        return 0.0
    b = (sigma - mu) / (sigma + mu)   # in [-1, 1]
    return max(0.0, (b + 1.0) / 2.0)  # map to [0,1]


# --- Individual detectors ------------------------------------------------------
def _detect_sentence_rhythm(sents: List[Sentence], cfg: dict) -> List[Flag]:
    c = cfg["sentence_rhythm"]
    flags: List[Flag] = []
    if len(sents) < c["min_sentences"]:
        return flags
    lengths = [float(s.word_count) for s in sents]
    cv = _cv(lengths)
    ac = _autocorr_lag1(lengths)
    doc_span = (sents[0].start, sents[-1].end)
    if cv < c["cv_flag_below"]:
        flags.append(Flag(
            factor="sentence_rhythm", scope="document",
            reason=f"Sentence-length coefficient of variation {cv:.3f} is below "
                   f"{c['cv_flag_below']} — sentences are too uniform in length.",
            metric=round(cv, 4), threshold=c["cv_flag_below"],
            span_start=doc_span[0], span_end=doc_span[1], span_text="[document]"))
    if ac > c["autocorr_lag1_flag_above"]:
        flags.append(Flag(
            factor="sentence_rhythm", scope="document",
            reason=f"Sentence-length lag-1 autocorrelation {ac:.3f} exceeds "
                   f"{c['autocorr_lag1_flag_above']} — a repetitive rhythm is present.",
            metric=round(ac, 4), threshold=c["autocorr_lag1_flag_above"],
            span_start=doc_span[0], span_end=doc_span[1], span_text="[document]"))
    return flags


def _detect_burstiness(sents: List[Sentence], text: str, cfg: dict) -> List[Flag]:
    c = cfg["burstiness"]
    flags: List[Flag] = []
    if len(sents) < c["min_sentences"]:
        return flags
    slen = [float(s.word_count) for s in sents]
    sb = _burstiness(slen)
    words = _WORD.findall(text)
    wlen = [float(len(w)) for w in words]
    wb = _burstiness(wlen)
    doc_span = (sents[0].start, sents[-1].end)
    if sb < c["sentence_burstiness_flag_below"]:
        flags.append(Flag(
            factor="burstiness", scope="document",
            reason=f"Sentence burstiness {sb:.3f} is below "
                   f"{c['sentence_burstiness_flag_below']} — lacks the short/long "
                   f"variation typical of human writing.",
            metric=round(sb, 4), threshold=c["sentence_burstiness_flag_below"],
            span_start=doc_span[0], span_end=doc_span[1], span_text="[document]"))
    if wb < c["word_burstiness_flag_below"]:
        flags.append(Flag(
            factor="burstiness", scope="document",
            reason=f"Word-length burstiness {wb:.3f} is below "
                   f"{c['word_burstiness_flag_below']} — word lengths are too even.",
            metric=round(wb, 4), threshold=c["word_burstiness_flag_below"],
            span_start=doc_span[0], span_end=doc_span[1], span_text="[document]"))
    return flags


def _detect_sentence_structure(sents: List[Sentence], cfg: dict) -> List[Flag]:
    c = cfg["sentence_structure"]
    flags: List[Flag] = []
    if len(sents) < c["min_sentences"]:
        return flags
    # (a) repeated opening bigram ratio
    bigrams = [s.opening_bigram for s in sents]
    counts = Counter(bigrams)
    most_common, freq = counts.most_common(1)[0]
    ratio = freq / len(sents)
    if ratio > c["opening_bigram_repeat_ratio_flag_above"] and freq >= 2:
        # flag each sentence sharing the dominant opening
        for s in sents:
            if s.opening_bigram == most_common:
                flags.append(Flag(
                    factor="sentence_structure", scope="sentence",
                    reason=f"Sentence opening '{most_common}' repeats in "
                           f"{freq}/{len(sents)} sentences (ratio {ratio:.2f} > "
                           f"{c['opening_bigram_repeat_ratio_flag_above']}).",
                    metric=round(ratio, 4),
                    threshold=c["opening_bigram_repeat_ratio_flag_above"],
                    span_start=s.start, span_end=s.end, span_text=s.text))
    # (b) runs of the same first token (>= same_first_token_run_flag_at in a row)
    run_start = 0
    for i in range(1, len(sents) + 1):
        same = i < len(sents) and sents[i].first_token == sents[run_start].first_token
        if not same:
            run_len = i - run_start
            if run_len >= c["same_first_token_run_flag_at"]:
                for j in range(run_start, i):
                    s = sents[j]
                    flags.append(Flag(
                        factor="sentence_structure", scope="sentence",
                        reason=f"{run_len} consecutive sentences start with "
                               f"'{sents[run_start].first_token}'.",
                        metric=float(run_len),
                        threshold=float(c["same_first_token_run_flag_at"]),
                        span_start=s.start, span_end=s.end, span_text=s.text))
            run_start = i
    return flags


def _detect_paragraph_pattern(sents: List[Sentence], text: str, cfg: dict) -> List[Flag]:
    c = cfg["paragraph_pattern"]
    flags: List[Flag] = []
    # group sentences by paragraph
    paras: Dict[int, List[Sentence]] = {}
    for s in sents:
        paras.setdefault(s.para_index, []).append(s)
    if len(paras) < c["min_paragraphs"]:
        return flags
    para_ids = sorted(paras)
    lengths = [float(len(paras[p])) for p in para_ids]   # sentences per paragraph
    cv = _cv(lengths)
    # parallel openings: fraction of paragraphs whose FIRST sentence shares the
    # same opening bigram as another paragraph's first sentence.
    first_openings = [paras[p][0].opening_bigram for p in para_ids]
    opening_counts = Counter(first_openings)
    parallel = sum(v for v in opening_counts.values() if v >= 2)
    parallel_ratio = parallel / len(para_ids)

    if cv < c["length_cv_flag_below"]:
        for p in para_ids:
            block = paras[p]
            flags.append(Flag(
                factor="paragraph_pattern", scope="paragraph",
                reason=f"Paragraph lengths are uniform (CV {cv:.3f} < "
                       f"{c['length_cv_flag_below']}) — mechanical paragraphing.",
                metric=round(cv, 4), threshold=c["length_cv_flag_below"],
                span_start=block[0].start, span_end=block[-1].end,
                span_text=text[block[0].start:block[-1].end]))
    if parallel_ratio > c["parallel_opening_ratio_flag_above"]:
        for p in para_ids:
            block = paras[p]
            if opening_counts[block[0].opening_bigram] >= 2:
                flags.append(Flag(
                    factor="paragraph_pattern", scope="paragraph",
                    reason=f"Paragraph opening '{block[0].opening_bigram}' is reused "
                           f"across paragraphs (parallel ratio {parallel_ratio:.2f} > "
                           f"{c['parallel_opening_ratio_flag_above']}).",
                    metric=round(parallel_ratio, 4),
                    threshold=c["parallel_opening_ratio_flag_above"],
                    span_start=block[0].start, span_end=block[-1].end,
                    span_text=text[block[0].start:block[-1].end]))
    return flags


def _detect_ngram_formula(sents: List[Sentence], text: str, cfg: dict) -> List[Flag]:
    c = cfg["ngram_formula"]
    flags: List[Flag] = []
    tokens_with_pos: List[Tuple[str, int, int]] = []
    for m in _WORD.finditer(text):
        tokens_with_pos.append((m.group(0).lower(), m.start(), m.end()))
    toks = [t[0] for t in tokens_with_pos]
    n_tokens = len(toks)
    for size in c["ngram_sizes"]:
        if n_tokens < size:
            continue
        grams: Dict[Tuple[str, ...], List[int]] = {}
        for i in range(n_tokens - size + 1):
            g = tuple(toks[i:i + size])
            if c.get("ignore_if_all_stopwords") and all(w in _STOPWORDS for w in g):
                continue
            grams.setdefault(g, []).append(i)
        for g, idxs in grams.items():
            repeats = len(idxs)
            fires = (repeats >= c["min_repeats_to_flag"]) or \
                    (size >= c["min_ngram_size_for_single_repeat"] and repeats >= 1 and repeats >= 2)
            # a single repeat of a long n-gram (>= min_ngram_size_for_single_repeat) counts
            if size >= c["min_ngram_size_for_single_repeat"]:
                fires = repeats >= c["min_repeats_to_flag"]
            if repeats >= c["min_repeats_to_flag"]:
                for start_i in idxs:
                    s_char = tokens_with_pos[start_i][1]
                    e_char = tokens_with_pos[start_i + size - 1][2]
                    flags.append(Flag(
                        factor="ngram_formula", scope="span",
                        reason=f"{size}-word formula \"{' '.join(g)}\" repeats "
                               f"{repeats} times.",
                        metric=float(repeats),
                        threshold=float(c["min_repeats_to_flag"]),
                        span_start=s_char, span_end=e_char,
                        span_text=text[s_char:e_char]))
    return flags


def _detect_transition_formula(sents: List[Sentence], cfg: dict) -> List[Flag]:
    c = cfg["transition_formula"]
    flags: List[Flag] = []
    connectives = [x.lower() for x in c["connectives"]]
    total = len(sents)
    if total == 0:
        return flags
    per_conn = Counter()
    hits: List[Tuple[str, Sentence]] = []
    for s in sents:
        low = s.text.lower().lstrip()
        for conn in connectives:
            if low.startswith(conn) or (" " + conn + " ") in (" " + low):
                # count only openers or clear formulaic use
                if low.startswith(conn):
                    per_conn[conn] += 1
                    hits.append((conn, s))
                    break
    total_ratio = len(hits) / total
    if total_ratio > c["max_total_ratio_flag_above"]:
        for conn, s in hits:
            flags.append(Flag(
                factor="transition_formula", scope="sentence",
                reason=f"Formulaic connective opener '{conn}' — connectives open "
                       f"{len(hits)}/{total} sentences (ratio {total_ratio:.2f} > "
                       f"{c['max_total_ratio_flag_above']}).",
                metric=round(total_ratio, 4),
                threshold=c["max_total_ratio_flag_above"],
                span_start=s.start, span_end=s.end, span_text=s.text))
    # per-connective overuse
    for conn, cnt in per_conn.items():
        if cnt > c["max_single_connective_count"]:
            for hc, s in hits:
                if hc == conn:
                    flags.append(Flag(
                        factor="transition_formula", scope="sentence",
                        reason=f"Connective '{conn}' opens {cnt} sentences "
                               f"(> {c['max_single_connective_count']}).",
                        metric=float(cnt),
                        threshold=float(c["max_single_connective_count"]),
                        span_start=s.start, span_end=s.end, span_text=s.text))
    return flags


# --- Public API ----------------------------------------------------------------
def _dedup_spans(flags: List[Flag]) -> List[Dict]:
    """
    Merge overlapping/duplicate flagged spans into a minimal set of character
    ranges to hand to Phase 2. Document-scope flags are excluded from span list
    (they mean 'rewrite is warranted' but don't point at one place); when only
    document flags exist we fall back to flagging every sentence span.
    """
    concrete = [f for f in flags if f.scope in ("sentence", "paragraph", "span")]
    ranges = sorted({(f.span_start, f.span_end) for f in concrete})
    merged: List[List[int]] = []
    for s, e in ranges:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    # attach the reasons/factors covering each merged range
    out = []
    for s, e in merged:
        covering = [f for f in concrete if not (f.span_end <= s or f.span_start >= e)]
        out.append({
            "start": s, "end": e,
            "factors": sorted({f.factor for f in covering}),
            "reasons": [f.reason for f in covering],
        })
    return out


def detect(text: str, config_path: Optional[str] = None) -> DetectionReport:
    cfg = _load_config(config_path)
    eng = cfg["engine"]
    words = _WORD.findall(text)
    sents = _parse(text)
    paras = len({s.para_index for s in sents})

    report = DetectionReport(
        flagged=False, word_count=len(words),
        sentence_count=len(sents), paragraph_count=paras,
    )

    if len(words) > eng["max_words"]:
        report.notes.append(
            f"Input {len(words)} words exceeds max_words {eng['max_words']}; "
            f"analysis still runs but consider chunking.")
    if len(words) < eng["min_words_to_analyze"]:
        report.notes.append(
            f"Input {len(words)} words below min_words_to_analyze "
            f"{eng['min_words_to_analyze']}; detection skipped (too short to be reliable).")
        return report

    all_flags: List[Flag] = []
    all_flags += _detect_ngram_formula(sents, text, cfg)
    all_flags += _detect_sentence_rhythm(sents, cfg)
    all_flags += _detect_burstiness(sents, text, cfg)
    all_flags += _detect_sentence_structure(sents, cfg)
    all_flags += _detect_paragraph_pattern(sents, text, cfg)
    all_flags += _detect_transition_formula(sents, cfg)

    # metrics summary (always computed, for transparency)
    slen = [float(s.word_count) for s in sents] or [0.0]
    wlen = [float(len(w)) for w in words] or [0.0]
    report.metrics = {
        "sentence_length_cv": round(_cv(slen), 4),
        "sentence_length_autocorr_lag1": round(_autocorr_lag1(slen), 4),
        "sentence_burstiness": round(_burstiness(slen), 4),
        "word_burstiness": round(_burstiness(wlen), 4),
        "mean_sentence_length": round(_mean(slen), 2),
    }

    report.flags = all_flags
    report.flagged = len(all_flags) > 0
    report.flagged_spans = _dedup_spans(all_flags)

    # If only document-level flags fired (rhythm/burstiness) but no concrete
    # span, hand Phase 2 every sentence so it can vary construction globally.
    if report.flagged and not report.flagged_spans:
        report.flagged_spans = [{
            "start": s.start, "end": s.end,
            "factors": sorted({f.factor for f in all_flags}),
            "reasons": [f.reason for f in all_flags if f.scope == "document"],
        } for s in sents]

    return report


if __name__ == "__main__":
    import sys
    src = sys.stdin.read() if not sys.argv[1:] else Path(sys.argv[1]).read_text()
    rep = detect(src)
    print(json.dumps(rep.to_dict(), indent=2))
