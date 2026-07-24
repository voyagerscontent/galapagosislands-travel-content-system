"""
Tests for the v1.4 context-trigger flagging layer.

These tests verify the FLAG-ONLY semantics:
- Context triggers detect AI structural patterns
- The engine does NOT substitute the matched text
- Candidate human_variants are attached, deterministically ordered
- The regex-substitution layer continues to work unchanged
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from humanizer import Humanizer  # noqa: E402
from humanizer.engine import FlaggedSpan  # noqa: E402


# ---------- loading ----------

def test_triggers_load_on_init():
    h = Humanizer()
    # v1.4 JSON has 21 triggers
    assert len(h.loaded_triggers) >= 20
    # Every id should be a string
    assert all(isinstance(tid, str) for tid in h.loaded_triggers)


def test_triggers_can_be_disabled():
    h = Humanizer(trigger_file=None)
    assert h.loaded_triggers == []
    # Sanity: humanize still returns a result with an empty flag list
    r = h.humanize("Whether you are a family or a solo traveler, there is something for everyone.")
    assert r.flagged_spans == []
    assert r.flag_count == 0


def test_dump_triggers_matches_loaded():
    h = Humanizer()
    dumped = h.dump_triggers()
    assert len(dumped) == len(h.loaded_triggers)
    for entry in dumped:
        assert "id" in entry
        assert "pattern" in entry
        assert "human_variants" in entry
        assert isinstance(entry["human_variants"], list)
        assert len(entry["human_variants"]) >= 1
        assert "instruction_to_llm" in entry


# ---------- flag_only behavior ----------

def test_context_trigger_does_not_substitute():
    """CRITICAL invariant: matched trigger text is left in the output text."""
    h = Humanizer()
    ai = ("Whether you're a family looking for adventure or a couple seeking "
          "romance, there is something for everyone in Galapagos.")
    r = h.humanize(ai)
    # At least one trigger should fire
    assert r.flag_count >= 1
    # The matched text of each flag must appear verbatim in the output text
    for span in r.flagged_spans:
        assert span.matched_text in r.text, (
            f"Trigger {span.trigger_id} matched text not preserved in output"
        )


def test_flagged_span_has_candidates_and_instruction():
    h = Humanizer()
    ai = "Our expert team will curate the perfect itinerary for your trip."
    r = h.humanize(ai)
    assert r.flag_count >= 1
    span = r.flagged_spans[0]
    assert isinstance(span, FlaggedSpan)
    assert span.candidate_variants  # non-empty
    assert len(span.candidate_variants) <= 6  # MAX_CANDIDATES_PER_FLAG
    assert span.llm_instruction  # non-empty string
    assert span.trigger_id
    assert span.topic_bucket


def test_flag_offsets_point_to_output_text():
    """Offsets in FlaggedSpan should slice out matched_text from result.text."""
    h = Humanizer()
    r = h.humanize(
        "Whether you love hiking or diving, there is something for everyone."
    )
    for span in r.flagged_spans:
        assert r.text[span.start:span.end] == span.matched_text


def test_context_before_and_after_populated():
    h = Humanizer()
    r = h.humanize(
        "Before context. Immerse yourself in the wonders of the Galapagos "
        "archipelago and its wildlife. After context here."
    )
    if r.flag_count == 0:
        # Regex layer may have consumed the phrase; skip
        return
    span = r.flagged_spans[0]
    # We expect some surrounding text (unless match sits at doc boundary)
    total_ctx = span.context_before + span.context_after
    assert len(total_ctx) > 0


# ---------- determinism ----------

def test_flagging_is_deterministic():
    """Same input twice -> same flagged spans in same order with same first variant."""
    h = Humanizer()
    ai = (
        "Whether you are new to travel or a seasoned explorer, there is "
        "something for everyone. Our expert team will craft the perfect "
        "itinerary. Book your adventure today and immerse yourself in the "
        "wonders of Galapagos."
    )
    r1 = h.humanize(ai)
    r2 = h.humanize(ai)
    assert r1.text == r2.text
    assert r1.flag_count == r2.flag_count
    assert [s.trigger_id for s in r1.flagged_spans] == [s.trigger_id for s in r2.flagged_spans]
    assert [s.candidate_variants[0] for s in r1.flagged_spans] == [
        s.candidate_variants[0] for s in r2.flagged_spans
    ]


def test_no_overlapping_flags():
    """De-overlap logic: no two flagged spans should overlap in the output."""
    h = Humanizer()
    ai = (
        "Whether you are a family or a solo traveler, there is something "
        "for everyone on this unforgettable experience. Our expert team "
        "will curate the perfect itinerary."
    )
    r = h.humanize(ai)
    spans = sorted(r.flagged_spans, key=lambda s: s.start)
    for a, b in zip(spans, spans[1:]):
        assert a.end <= b.start, (
            f"Overlap: {a.trigger_id}[{a.start}-{a.end}] vs "
            f"{b.trigger_id}[{b.start}-{b.end}]"
        )


# ---------- coexistence with regex layer ----------

def test_regex_replacement_still_works_when_triggers_active():
    """Regression: v1.1 behavior must still hold with triggers loaded."""
    h = Humanizer()
    r = h.humanize("We will delve into the details.")
    assert "delve" not in r.text.lower()
    assert r.replacement_count >= 1


def test_landing_craft_regex_and_trigger_coexist():
    """panga is protected vocab; 'inflatable craft' regex-swaps to landing terms."""
    h = Humanizer()
    r = h.humanize(
        "We took the panga to shore. Then the inflatable craft came back for us."
    )
    assert "panga" in r.text  # protected
    # 'inflatable craft' -> panga/dinghy/zodiac/small boat via variants
    assert "inflatable craft" not in r.text.lower()


# ---------- serialization ----------

def test_to_dict_includes_flagged_spans():
    h = Humanizer()
    r = h.humanize("Whether you're new or experienced, there is something for everyone.")
    d = r.to_dict()
    assert "flagged_spans" in d
    assert "flag_count" in d
    assert d["flag_count"] == len(d["flagged_spans"])
    if d["flag_count"] > 0:
        first = d["flagged_spans"][0]
        # All expected keys
        for k in ("trigger_id", "matched_text", "start", "end",
                  "candidate_variants", "llm_instruction",
                  "context_before", "context_after",
                  "topic_bucket", "reason"):
            assert k in first, f"missing key {k}"


def test_result_is_json_serializable():
    h = Humanizer()
    r = h.humanize("Immerse yourself in the wonders of the Galapagos archipelago.")
    # Must round-trip through JSON without exceptions
    s = json.dumps(r.to_dict())
    assert len(s) > 10


# ---------- variant schema tolerance ----------

def test_variant_schema_object_or_string(tmp_path):
    """The loader must accept both {'text': ...} and bare strings."""
    dict_dir = tmp_path / "dict"
    dict_dir.mkdir()
    # Minimal required core files
    for name in ("core_words.json", "core_phrases.json", "travel_words.json",
                 "travel_phrases.json"):
        (dict_dir / name).write_text(json.dumps({"replacements": {}}))
    # Custom trigger file mixing both schemas
    triggers = {
        "_meta": {"version": "test"},
        "triggers": [
            {
                "id": "test_trigger",
                "trigger_pattern": r"(?i)\btest phrase\b",
                "topic_bucket": "test",
                "reason": "test",
                "instruction_to_llm": "test",
                "human_variants": [
                    "bare string variant",
                    {"text": "object variant", "source": "curated"},
                ],
            }
        ],
    }
    (dict_dir / "travel_context_triggers.json").write_text(json.dumps(triggers))
    h = Humanizer(dict_dir=dict_dir)
    assert "test_trigger" in h.loaded_triggers
    r = h.humanize("This is a test phrase in context.")
    assert r.flag_count == 1
    variants = r.flagged_spans[0].candidate_variants
    assert "bare string variant" in variants
    assert "object variant" in variants
