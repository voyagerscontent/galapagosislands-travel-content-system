"""
Tests for Phase 1 (deterministic detector) and the fact-safety guard.

These require NO API key and NO network — they prove the deterministic core.
Run:  python3 -m pytest tests/ -q   (or: python3 tests/test_detector.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from detector.detector import detect
from restructurer import factguard
from restructurer.markov import MarkovExtender

AI_TEXT = (
    "The Galapagos Islands offer a unique experience for travelers. "
    "The islands provide stunning wildlife encounters for visitors. "
    "The archipelago delivers unforgettable moments for everyone. "
    "The destination creates lasting memories for guests.\n\n"
    "Moreover, the tours are designed to maximize your comfort. "
    "Furthermore, the guides are trained to enhance your journey. "
    "Additionally, the boats are equipped to ensure your safety. "
    "In conclusion, the experience is crafted to exceed your expectations."
)

HUMAN_TEXT = (
    "We got to Santa Cruz around noon, exhausted. The ferry had been late "
    "again and honestly by then I just wanted a bed.\n\n"
    "But then a sea lion flopped onto the dock right next to us, completely "
    "indifferent, and everything changed. My daughter shrieked. The captain "
    "laughed. Suddenly nobody cared about the delay. Galapagos does that. It "
    "ambushes you, and you forget what year it is while watching an iguana "
    "sneeze salt into the wind. Bring good shoes. The rest sorts itself out."
)


def test_ai_text_is_flagged():
    rep = detect(AI_TEXT)
    assert rep.flagged is True
    factors = {f.factor for f in rep.flags}
    # the mechanical sample should trip multiple pattern detectors
    assert "sentence_rhythm" in factors
    assert "transition_formula" in factors
    assert len(rep.flagged_spans) >= 1


def test_human_text_not_flagged():
    rep = detect(HUMAN_TEXT)
    # varied human writing should not trip the pattern detectors
    factors = {f.factor for f in rep.flags}
    assert "sentence_rhythm" not in factors
    assert "sentence_structure" not in factors
    assert "paragraph_pattern" not in factors


def test_determinism():
    a = detect(AI_TEXT).to_dict()
    b = detect(AI_TEXT).to_dict()
    assert a == b, "detector must be deterministic"


def test_short_text_skipped():
    rep = detect("Too short to judge.")
    assert rep.flagged is False
    assert any("below min_words" in n for n in rep.notes)


def test_factguard_rejects_new_number():
    o = "We spent 3 nights aboard the Beluga."
    r = "We spent 5 nights aboard the Beluga."
    g = factguard.check(o, r)
    assert g.ok is False
    assert "5" in "".join(g.new_numbers)


def test_factguard_rejects_new_entity():
    o = "Our guide showed us the island."
    r = "Our guide Fernando showed us the island near Isabela."
    g = factguard.check(o, r)
    assert g.ok is False
    assert any(e in ("Fernando", "Isabela") for e in g.new_entities)


def test_factguard_allows_spelled_number_paraphrase():
    o = "We spent 3 nights aboard the boat."
    r = "Three nights aboard the boat, and every one counted."
    g = factguard.check(o, r)
    assert g.ok is True          # 3 == three, no new fact
    assert g.major_change is False


def test_factguard_clean_reword():
    o = "The wildlife is diverse and abundant here."
    r = "Diverse, abundant wildlife everywhere you look."
    g = factguard.check(o, r)
    assert g.ok is True


def test_markov_is_seed_deterministic_and_ontopic():
    m1 = MarkovExtender(AI_TEXT, corpus_bucket_keywords=["galapagos", "general"])
    m2 = MarkovExtender(AI_TEXT, corpus_bucket_keywords=["galapagos", "general"])
    a = m1.cadence_seeds(seed_salt="x")
    b = m2.cadence_seeds(seed_salt="x")
    c = m1.cadence_seeds(seed_salt="y")
    assert a == b            # same salt => reproducible
    assert a != c            # different salt => different (non-patterned)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} tests passed")
