"""Module + end-to-end tests. Run: PYTHONPATH=content-pipeline python -m pytest (or this file)."""
from content_pipeline.macro_guardrail import macro
from content_pipeline.micro_guardrail import micro
from content_pipeline.lexical_injector import injector as lex
from content_pipeline.voice_guard import voice_guard as vg
from content_pipeline.orchestrator import pipeline

UNIFORM = "\n\n".join([" ".join(["word"] * 90) + ". Two three. Four five. Six seven." for _ in range(6)])
BURSTY_LENS = [18, 140, 45, 8, 190, 60, 25, 110]
BURSTY = "\n\n".join(" ".join(["word"] * L) + (". x" * (1 + L // 40)) for L in BURSTY_LENS)


def test_macro_rejects_uniform_passes_bursty():
    assert macro.evaluate(UNIFORM).passed is False
    assert macro.evaluate(BURSTY).passed is True
    x = b"A" * 500                                        # realistic size (gzip overhead amortized)
    assert macro.ncd(x, x) < macro.ncd(x, bytes(range(256)) * 3)   # identical closer than dissimilar


def test_macro_rewrite_loop_capped():
    calls = {"n": 0}
    def rewrite(sec, res):
        calls["n"] += 1
        return sec                                        # never improves
    _, res, attempts = macro.enforce(UNIFORM, rewrite, max_retries=3)
    assert attempts == 3 and calls["n"] == 3 and res.passed is False


def test_micro_raises_cv_and_preserves_paragraphs():
    text = "\n\n".join(["We saw the birds over the bay today. The guide told us about the flows. "
                        "Lunch was ready aboard the boat. The swim was cool and clear later on."] * 2)
    r = micro.enforce(text)
    assert r.paragraphs_in == r.paragraphs_out == 2       # HARD invariant
    assert r.cv_after >= r.cv_before


def test_lexical_injector_replaces_and_salts_preserving_paragraphs():
    text = ("The snorkel was amazing and the water was pristine. We could see the fish. "
            "Sea lions swam close to explore the divers.\n\n"
            "The panga ride to the remote cove felt peaceful. The birds were incredible. "
            "You enjoy the quiet highlands.")
    r = lex.inject(text)
    assert r.paragraphs_in == r.paragraphs_out
    assert len(r.replacements) >= 4                       # generic JJ/VB swapped (POS-confirmed)
    assert r.salted_paragraphs >= 1                       # human sentence spliced in
    assert r.text != text                                 # injection changed the text


def test_voice_guard_section_by_section():
    cfg = vg.VoiceConfig()
    sp = vg.build_system_prompt(cfg)
    assert "ONE SECTION AT A TIME" in sp and "300" in sp and "600" in sp
    outline = [{"key": "intro", "title": "Intro", "brief": "x"},
               {"key": "body", "title": "Body", "brief": "y"}]
    seen = []
    def llm(system, user):
        seen.append(user)
        return " ".join(["word"] * 400)                   # in-range section
    secs = vg.generate_article(outline, llm, cfg)
    assert len(secs) == 2 and all(s.within_range for s in secs)
    assert len(seen) == 2                                  # one call per section


def test_orchestrator_end_to_end():
    outline = [{"key": f"s{i}", "title": f"S{i}", "brief": "b"} for i in range(3)]
    # fake LLM returns a bursty section so macro passes first try
    def llm(system, user):
        return BURSTY
    def rewrite(sec, res):
        return BURSTY
    def humanize(article):
        return article
    res = pipeline.run(outline, llm, rewrite, humanize=humanize)
    assert len(res.sections) == 3
    assert res.injection is not None
    assert res.article                                     # non-empty final article
    # lexical injection ran at the very end
    assert res.injection.paragraphs_in == res.injection.paragraphs_out


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}"); passed += 1
        except Exception:
            print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
