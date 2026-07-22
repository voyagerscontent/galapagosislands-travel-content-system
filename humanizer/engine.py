"""
Hardcoded, deterministic humanizer engine — v1.1 with variant support.

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
class HumanizeResult:
    text: str
    original_text: str
    replacements: List[Replacement] = field(default_factory=list)
    word_count: int = 0
    replacement_count: int = 0
    truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "original_text": self.original_text,
            "word_count": self.word_count,
            "replacement_count": self.replacement_count,
            "truncated": self.truncated,
            "replacements": [r.to_dict() for r in self.replacements],
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
    ) -> None:
        self.dict_dir = Path(dict_dir) if dict_dir else DICT_DIR
        self.max_words = int(max_words)
        self.seed = seed
        # Each source stores: (name, compiled_pattern, {lower_key: [variants]})
        self._sources: List[Tuple[str, re.Pattern, Dict[str, List[str]]]] = []
        self._loaded_names: List[str] = []

        files = dictionaries if dictionaries is not None else DEFAULT_DICT_FILES
        for filename in files:
            self._load_dict_file(filename)

        if extra_dicts:
            self._add_dict("extra_dicts", extra_dicts)

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

    @property
    def loaded_dictionaries(self) -> List[str]:
        return list(self._loaded_names)

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

        return HumanizeResult(
            text=current,
            original_text=original,
            replacements=replacements,
            word_count=word_count,
            replacement_count=len(replacements),
            truncated=truncated,
        )

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
