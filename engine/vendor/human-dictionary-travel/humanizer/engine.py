"""
Hardcoded, deterministic humanizer engine — v1.4 with context-trigger layer.

- No LLM. No network.
- Pre-compiled regex tables from JSON dictionaries.
- Word-boundary safe, case-preserving, phrase-first / longest-first ordering.
- 3,000-word hard input cap (configurable).

v1.1: variant-aware.
- A dictionary value can be either a string (single replacement) OR an array
  of strings (multiple human alternatives).
- When multiple variants exist, the engine picks one per occurrence using a
  seeded Markov-style state machine so results are:
    (a) DETERMINISTIC for a given input   (no LLM, no true randomness), AND
    (b) NON-PATTERNED across occurrences (avoids "same phrase every time").
- The picker chains state on a hash of (previous_pick, surrounding_context)
  so the same AI phrase in different contexts yields different variants, and
  the previous pick influences the next one — a first-order Markov walk over
  the variant list.

v1.4: context-trigger layer.
- travel_context_triggers.json defines AI structural patterns that cannot be
  cleanly regex-swapped (whole-sentence tropes, phrases needing sentence
  reshape). The engine FLAGS these matches but does not substitute — a
  downstream LLM step (n8n OpenAI HTTP node) rewrites the flagged sentence,
  pasting one of the pre-approved human_variants character-for-character.
- Engine emits `flagged_spans` in the result with the trigger id, matched
  text, char range, local context (~40 chars before + after), an ordered
  candidate list of human variants (Markov-picked so it's deterministic),
  and the LLM instruction. Downstream consumers see everything they need
  to call OpenAI with a strict verbatim guardrail.
- No LLM is called from the Python engine itself — this stays 100% offline.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

MAX_WORDS = 3000

DICT_DIR = Path(__file__).resolve().parent.parent / "dictionary"

# Order matters: phrases first (longer -> shorter), then words.
# travel_variants.json is loaded FIRST so its variant-aware replacements
# take priority over the single-value travel_phrases.json.
DEFAULT_DICT_FILES = [
    "travel_variants.json",  # variant-aware travel phrases (highest priority)
    "travel_phrases.json",   # single-value travel phrases
    "core_phrases.json",     # universal phrases
    "travel_words.json",     # domain words
    "core_words.json",       # universal words
]

# Context-trigger file: flag-only, no substitution here.
DEFAULT_TRIGGER_FILE = "travel_context_triggers.json"
# Max human_variants offered to the LLM per flagged span. Kept small so
# prompts stay short and the LLM's verbatim-copy job is easier.
MAX_CANDIDATES_PER_FLAG = 6


@dataclass
class Replacement:
    original: str
    replacement: str
    start: int
    end: int
    source: str
    variant_index: int = 0  # which variant was picked (0 if no variants)
    variant_count: int = 1  # how many variants were available

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "replacement": self.replacement,
            "start": self.start,
            "end": self.end,
            "source": self.source,
            "variant_index": self.variant_index,
            "variant_count": self.variant_count,
        }


@dataclass
class FlaggedSpan:
    """A context-trigger match. The engine does NOT substitute; downstream
    LLM (n8n OpenAI node) rewrites the sentence pasting one of the
    candidate_variants verbatim. If the LLM output does not contain a
    candidate verbatim, the flagged text is left as-is (safe fallback)."""
    trigger_id: str
    matched_text: str
    start: int
    end: int
    context_before: str
    context_after: str
    candidate_variants: List[str]  # Markov-ordered subset (top N)
    llm_instruction: str
    topic_bucket: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "trigger_id": self.trigger_id,
            "matched_text": self.matched_text,
            "start": self.start,
            "end": self.end,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "candidate_variants": self.candidate_variants,
            "llm_instruction": self.llm_instruction,
            "topic_bucket": self.topic_bucket,
            "reason": self.reason,
        }


@dataclass
class HumanizeResult:
    text: str
    original_text: str
    replacements: List[Replacement] = field(default_factory=list)
    flagged_spans: List[FlaggedSpan] = field(default_factory=list)
    word_count: int = 0
    replacement_count: int = 0
    flag_count: int = 0
    truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "original_text": self.original_text,
            "word_count": self.word_count,
            "replacement_count": self.replacement_count,
            "flag_count": self.flag_count,
            "truncated": self.truncated,
            "replacements": [r.to_dict() for r in self.replacements],
            "flagged_spans": [f.to_dict() for f in self.flagged_spans],
        }


def _count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _preserve_case(source: str, replacement: str) -> str:
    if not replacement:
        return ""
    if not source:
        return replacement
    stripped_src = source.strip()
    stripped_rep = replacement
    if stripped_src.isupper() and any(c.isalpha() for c in stripped_src):
        return stripped_rep.upper()
    first_alpha = next((c for c in stripped_src if c.isalpha()), "")
    if first_alpha.isupper():
        for i, c in enumerate(stripped_rep):
            if c.isalpha():
                return stripped_rep[:i] + c.upper() + stripped_rep[i + 1:]
        return stripped_rep
    return stripped_rep


def _stable_hash(*parts: str) -> int:
    """Deterministic 63-bit hash across Python runs (unlike built-in hash())."""
    h = hashlib.blake2b(digest_size=8)
    for p in parts:
        h.update(p.encode("utf-8", errors="replace"))
        h.update(b"\x1f")
    return int.from_bytes(h.digest(), "big") & ((1 << 63) - 1)


class MarkovVariantPicker:
    """
    First-order Markov walker over the variant list of one AI phrase.

    - Each state is the previously-chosen variant index.
    - Transitions are computed on the fly from a stable hash of:
        (key, prev_index, occurrence_index, local_context)
      so the picker is fully deterministic given the input text but avoids
      choosing the same variant twice in a row (unless only one exists).

    - The transition never repeats the previous state when >1 variant exists,
      so consecutive replacements of the same AI phrase always differ. Beyond
      that, the walk explores all variants roughly evenly across a document.
    """

    __slots__ = ("_state", "_seed")

    def __init__(self, seed: str = "") -> None:
        # per-key state: key -> (previous_index, occurrence_counter)
        self._state: Dict[str, Tuple[int, int]] = {}
        self._seed = seed or ""

    def pick(self, key: str, variants: List[str], context: str) -> Tuple[int, str]:
        n = len(variants)
        if n == 0:
            return 0, ""
        if n == 1:
            return 0, variants[0]

        prev_idx, occ = self._state.get(key, (-1, 0))
        # Deterministic transition hash
        h = _stable_hash(self._seed, key, str(prev_idx), str(occ), context[-64:])
        # Build the candidate set, excluding prev_idx to guarantee non-repeat
        candidates = [i for i in range(n) if i != prev_idx]
        if not candidates:
            candidates = list(range(n))
        chosen = candidates[h % len(candidates)]
        self._state[key] = (chosen, occ + 1)
        return chosen, variants[chosen]


class Humanizer:
    """
    Deterministic AI-quirk humanizer with variant support.

    Usage:
        h = Humanizer()
        result = h.humanize(text)

    Kwargs:
        dictionaries: ordered list of filenames (defaults to DEFAULT_DICT_FILES)
        dict_dir:     override dictionary directory
        extra_dicts:  optional {"word": "rep" or ["rep1", "rep2"]}
        max_words:    hard word cap (default 3000)
        seed:         string seed for the Markov picker (default "": stable
                      per-input determinism; change per user or per doc to
                      get different but still-deterministic variant walks)
    """

    def __init__(
        self,
        dictionaries: Optional[List[str]] = None,
        dict_dir: Optional[Path] = None,
        extra_dicts: Optional[Dict[str, Union[str, List[str]]]] = None,
        max_words: int = MAX_WORDS,
        seed: str = "",
        trigger_file: Optional[str] = DEFAULT_TRIGGER_FILE,
    ) -> None:
        self.dict_dir = Path(dict_dir) if dict_dir else DICT_DIR
        self.max_words = int(max_words)
        self.seed = seed
        # Each source stores: (name, compiled_pattern, {lower_key: [variants]})
        self._sources: List[Tuple[str, re.Pattern, Dict[str, List[str]]]] = []
        self._loaded_names: List[str] = []
        # Context triggers: list of compiled dicts with regex + metadata
        self._triggers: List[dict] = []

        files = dictionaries if dictionaries is not None else DEFAULT_DICT_FILES
        for filename in files:
            self._load_dict_file(filename)

        if extra_dicts:
            self._add_dict("extra_dicts", extra_dicts)

        if trigger_file:
            self._load_triggers(trigger_file)

    # ----- dictionary loading -----

    def _load_dict_file(self, filename: str) -> None:
        path = self.dict_dir / filename
        if not path.exists():
            # travel_variants.json is optional
            if filename == "travel_variants.json":
                return
            raise FileNotFoundError(f"Dictionary file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        mapping = data.get("replacements", {})
        self._add_dict(filename, mapping)

    def _add_dict(
        self,
        name: str,
        mapping: Dict[str, Union[str, List[str]]],
    ) -> None:
        if not mapping:
            return
        # Normalize every value to a list of variants
        normalized: Dict[str, List[str]] = {}
        for k, v in mapping.items():
            if isinstance(v, list):
                variants = [str(x) for x in v] or [""]
            else:
                variants = [str(v)]
            normalized[k.lower()] = variants

        # Sort keys by length desc so longer phrases match first
        keys_sorted = sorted(normalized.keys(), key=lambda k: (-len(k), k))
        escaped = [re.escape(k) for k in keys_sorted]
        pattern = re.compile(
            r"(?<!\w)(" + "|".join(escaped) + r")(?!\w)",
            re.IGNORECASE,
        )
        self._sources.append((name, pattern, normalized))
        self._loaded_names.append(name)

    def _load_triggers(self, filename: str) -> None:
        """Load context-trigger definitions. Missing file is OK."""
        path = self.dict_dir / filename
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for t in data.get("triggers", []):
            try:
                rx = re.compile(t["trigger_pattern"])
            except re.error:
                continue
            # Normalize variants: accept list[str] or list[{text, source}]
            variants: List[str] = []
            for v in t.get("human_variants", []):
                if isinstance(v, str):
                    variants.append(v)
                elif isinstance(v, dict) and "text" in v:
                    variants.append(v["text"])
            if not variants:
                continue
            self._triggers.append({
                "id": t["id"],
                "pattern": rx,
                "topic_bucket": t.get("topic_bucket", "general"),
                "reason": t.get("reason", ""),
                "instruction": t.get("instruction_to_llm", ""),
                "variants": variants,
            })

    @property
    def loaded_dictionaries(self) -> List[str]:
        return list(self._loaded_names)

    @property
    def loaded_triggers(self) -> List[str]:
        return [t["id"] for t in self._triggers]

    def total_entries(self) -> int:
        return sum(len(m) for _, _, m in self._sources)

    def total_variants(self) -> int:
        return sum(len(v) for _, _, m in self._sources for v in m.values())

    # ----- core replace -----

    def humanize(self, text: str) -> HumanizeResult:
        if text is None:
            text = ""
        original = text
        word_count = _count_words(text)
        truncated = False
        if word_count > self.max_words:
            tokens = re.findall(r"\S+|\s+", text)
            kept: List[str] = []
            count = 0
            for tok in tokens:
                if tok.strip():
                    if count >= self.max_words:
                        break
                    count += 1
                kept.append(tok)
            text = "".join(kept)
            truncated = True
            word_count = self.max_words

        # Per-run picker so seed drives the Markov walk over this document
        picker = MarkovVariantPicker(seed=self.seed or _stable_hash(text[:256]).__str__())

        replacements: List[Replacement] = []
        current = text

        for source_name, pattern, variant_map in self._sources:
            def _sub(match: re.Match,
                     _src=source_name,
                     _vmap=variant_map,
                     _picker=picker) -> str:
                matched = match.group(0)
                key = matched.lower()
                variants = _vmap.get(key)
                if variants is None:
                    return matched
                # Context = ~40 chars around match for Markov state entropy
                start = max(0, match.start() - 32)
                end = min(len(match.string), match.end() + 32)
                context = match.string[start:end]
                v_idx, chosen = _picker.pick(key, variants, context)
                cased = _preserve_case(matched, chosen)
                replacements.append(
                    Replacement(
                        original=matched,
                        replacement=cased,
                        start=match.start(),
                        end=match.end(),
                        source=_src,
                        variant_index=v_idx,
                        variant_count=len(variants),
                    )
                )
                return cased

            current = pattern.sub(_sub, current)

        # Cleanup
        current = re.sub(r"[ \t]{2,}", " ", current)
        current = re.sub(r" +([,.!?;:])", r"\1", current)
        current = re.sub(r"(^|\n)[ \t]*[,;][ \t]*", r"\1", current)
        current = re.sub(r"\n[ \t]+\n", "\n\n", current)

        # ---- Context-trigger flagging pass (no substitution) ----
        flagged_spans = self._flag_context_triggers(current, picker)

        return HumanizeResult(
            text=current,
            original_text=original,
            replacements=replacements,
            flagged_spans=flagged_spans,
            word_count=word_count,
            replacement_count=len(replacements),
            flag_count=len(flagged_spans),
            truncated=truncated,
        )

    def _flag_context_triggers(
        self,
        text: str,
        picker: "MarkovVariantPicker",
    ) -> List[FlaggedSpan]:
        """Scan text for context-trigger regex matches. Emit FlaggedSpan for
        each; do NOT modify text. Overlapping matches are resolved by
        keeping the first (leftmost) longest match per position.
        """
        if not self._triggers:
            return []
        # Collect all matches
        raw: List[Tuple[int, int, dict, str]] = []
        for trig in self._triggers:
            for m in trig["pattern"].finditer(text):
                if m.start() == m.end():
                    continue
                raw.append((m.start(), m.end(), trig, m.group(0)))
        # Sort by (start, -length) so longest wins at same position
        raw.sort(key=lambda t: (t[0], -(t[1] - t[0])))
        # De-overlap: skip any match that overlaps a previously-kept one
        kept: List[Tuple[int, int, dict, str]] = []
        cursor = 0
        for start, end, trig, txt in raw:
            if start < cursor:
                continue
            kept.append((start, end, trig, txt))
            cursor = end

        # Build FlaggedSpan list with Markov-picked candidate ordering.
        # The picker gives each span a deterministic but non-patterned
        # first-choice variant; we surface the top MAX_CANDIDATES_PER_FLAG
        # so the LLM has options if the first doesn't fit grammatically.
        spans: List[FlaggedSpan] = []
        for start, end, trig, matched in kept:
            ctx_before = text[max(0, start - 80):start]
            ctx_after = text[end:min(len(text), end + 80)]
            variants = trig["variants"]
            # Order candidates: first the Markov pick, then the rest
            # (rotated so consecutive triggers of same id don't repeat).
            first_idx, _first = picker.pick(
                f"trigger:{trig['id']}",
                variants,
                ctx_before + ctx_after,
            )
            ordered = [variants[first_idx]] + [
                variants[i] for i in range(len(variants)) if i != first_idx
            ]
            spans.append(FlaggedSpan(
                trigger_id=trig["id"],
                matched_text=matched,
                start=start,
                end=end,
                context_before=ctx_before,
                context_after=ctx_after,
                candidate_variants=ordered[:MAX_CANDIDATES_PER_FLAG],
                llm_instruction=trig["instruction"],
                topic_bucket=trig["topic_bucket"],
                reason=trig["reason"],
            ))
        return spans

    # ----- utilities -----

    def dump_regex_rules(self) -> List[dict]:
        """
        Export flat rules for other runtimes (n8n JS, browser JS).
        For variants, all alternatives are exported so downstream runtimes
        can run the same Markov walker (see n8n_workflow_code_node.json
        and intake/index.html).
        """
        rules: List[dict] = []
        for source_name, _pattern, variant_map in self._sources:
            keys_sorted = sorted(variant_map.keys(), key=lambda k: (-len(k), k))
            for k in keys_sorted:
                variants = variant_map[k]
                rules.append({
                    "source": source_name,
                    "pattern": r"(?<!\w)" + re.escape(k) + r"(?!\w)",
                    "flags": "gi",
                    "key": k,
                    "variants": variants,
                    "replacement": variants[0],  # fallback for legacy consumers
                })
        return rules

    def dump_triggers(self) -> List[dict]:
        """Export context triggers for downstream runtimes (n8n Code node,
        intake page). Each entry ships its full variant list — the n8n
        OpenAI node will pick and validate verbatim inclusion.
        """
        out: List[dict] = []
        for t in self._triggers:
            out.append({
                "id": t["id"],
                "pattern": t["pattern"].pattern,
                "topic_bucket": t["topic_bucket"],
                "reason": t["reason"],
                "instruction_to_llm": t["instruction"],
                "human_variants": t["variants"],
            })
        return out
