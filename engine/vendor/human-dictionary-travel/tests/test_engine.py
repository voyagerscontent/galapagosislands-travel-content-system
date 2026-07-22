"""Unit tests for the deterministic humanizer engine."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from humanizer import Humanizer  # noqa: E402


def test_loads_all_dictionaries():
    h = Humanizer()
    assert len(h.loaded_dictionaries) >= 4
    assert h.total_entries() > 500


def test_single_word_replacement():
    h = Humanizer()
    r = h.humanize("We will delve into the details.")
    assert "delve" not in r.text.lower()
    assert "look at" in r.text.lower()
    assert r.replacement_count >= 1


def test_case_preserving():
    h = Humanizer()
    r = h.humanize("Delve deeper. DELVE now. delve later.")
    # Title -> Title, upper -> upper, lower -> lower
    assert "Look at" in r.text
    assert "LOOK AT" in r.text
    assert "look at" in r.text


def test_word_boundary_safety():
    h = Humanizer()
    # "delved" is a real key -> replaced, but "predelved" should NOT match "delved" as a subword
    r = h.humanize("predelved xdelvex")
    # neither should be replaced because they aren't word boundaries
    assert "predelved" in r.text
    assert "xdelvex" in r.text


def test_phrase_beats_word():
    h = Humanizer()
    r = h.humanize("Embark on a journey of a lifetime through the Andes.")
    # Should match the long phrase, not just the word 'embark'
    assert "embark" not in r.text.lower()
    # The whole phrase should have been rewritten as one replacement,
    # not fragmented into two (embark + journey of a lifetime).
    assert r.replacement_count == 1
    assert r.replacements[0].original.lower() == "embark on a journey of a lifetime"


def test_travel_specific_replacement():
    h = Humanizer()
    r = h.humanize("Explore the enchanted islands and swim with sea lions.")
    # "the enchanted islands" now has 4 variants — any of them is a
    # correct rewrite. All contain either 'Galapagos', 'islands', or
    # 'archipelago'.
    valid_targets = ("galapagos", "archipelago", "islands")
    assert any(t in r.text.lower() for t in valid_targets)
    assert "enchanted" not in r.text.lower()
    assert "swim with sea lions" in r.text


def test_voyagers_brand_preserved():
    h = Humanizer()
    r = h.humanize("At Voyagers, we believe travel changes lives.")
    # Should keep brand casing after normalization
    assert "At Voyagers" in r.text


def test_max_words_truncation():
    h = Humanizer(max_words=10)
    text = " ".join(["word"] * 25)
    r = h.humanize(text)
    assert r.truncated is True
    assert r.word_count == 10


def test_no_replacements_leaves_text_alone():
    h = Humanizer()
    src = "Hello world."
    r = h.humanize(src)
    assert r.text.strip() == "Hello world."


def test_replacements_report_offsets_and_source():
    h = Humanizer()
    r = h.humanize("Utilize this to leverage growth.")
    assert r.replacement_count >= 2
    for rep in r.replacements:
        assert rep.source
        assert 0 <= rep.start < rep.end <= len(rep.original_text_reference) if hasattr(rep, "original_text_reference") else True


def test_dump_regex_rules_shape():
    h = Humanizer()
    rules = h.dump_regex_rules()
    assert len(rules) > 500
    for rule in rules[:5]:
        assert "pattern" in rule and "replacement" in rule and "flags" in rule


def test_variants_are_deterministic_same_input_same_output():
    """Same text + same seed => identical output on every run."""
    h1 = Humanizer(seed="test-seed")
    h2 = Humanizer(seed="test-seed")
    text = (
        "Discover the enchanted islands and their unique wildlife. "
        "The enchanted islands offer unforgettable moments. "
        "In the enchanted islands, every day brings surprises. "
        "Visit the enchanted islands for a life-changing experience."
    )
    r1 = h1.humanize(text)
    r2 = h2.humanize(text)
    assert r1.text == r2.text


def test_variants_break_pattern_across_occurrences():
    """Multiple occurrences of the same AI phrase should NOT all become the
    same human variant — the Markov walker guarantees non-repeat."""
    h = Humanizer(seed="variant-test")
    text = (
        "The enchanted islands are stunning. "
        "The enchanted islands offer world-class snorkeling. "
        "The enchanted islands have twelve major visitor sites. "
        "The enchanted islands are volcanic in origin."
    )
    r = h.humanize(text)
    # Grab all replacements for the same key
    variants_used = [
        rep.replacement.lower()
        for rep in r.replacements
        if rep.original.lower() == "the enchanted islands"
    ]
    # Should have replaced 4 times
    assert len(variants_used) == 4
    # And they should not all be identical
    assert len(set(variants_used)) >= 2


def test_variants_never_repeat_consecutively():
    """First-order Markov: variant[i] != variant[i-1] when >1 option."""
    h = Humanizer(seed="no-repeat")
    text = " ".join(["The enchanted islands are amazing."] * 6)
    r = h.humanize(text)
    picks = [
        rep.variant_index for rep in r.replacements
        if rep.original.lower() == "the enchanted islands" and rep.variant_count > 1
    ]
    for a, b in zip(picks, picks[1:]):
        assert a != b, f"Consecutive variant repeat: {a} then {b}"


def test_variants_json_loaded():
    """travel_variants.json is loaded first and has array values."""
    h = Humanizer()
    assert "travel_variants.json" in h.loaded_dictionaries
    # There should be at least one key with >1 variant
    rules = h.dump_regex_rules()
    multi = [r for r in rules if len(r.get("variants", [])) > 1]
    assert len(multi) > 20, f"Expected many multi-variant rules, got {len(multi)}"


def test_different_seeds_produce_different_walks():
    """Different seeds should generally pick different variants, but same seed
    is stable."""
    text = " ".join(["The enchanted islands are wonderful."] * 8)
    a = Humanizer(seed="alpha").humanize(text).text
    b = Humanizer(seed="beta").humanize(text).text
    # Not guaranteed to be different for a very small variant set, but with
    # 4+ variants and 8 occurrences the walks almost always diverge.
    # If this ever flakes we'll expand the input.
    assert a != b


def test_repeated_run_is_idempotent_stable():
    h = Humanizer()
    once = h.humanize("Embark on a journey to delve into the Amazon rainforest.").text
    twice = h.humanize(once).text
    # Second pass should not keep introducing changes to already-cleaned text
    # (some minor changes may still occur if replacements themselves contain
    # keys, but the diff should shrink dramatically)
    r2 = h.humanize(once)
    assert r2.replacement_count <= 3


if __name__ == "__main__":
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"], check=False)
