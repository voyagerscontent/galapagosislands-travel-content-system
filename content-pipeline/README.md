# content-pipeline

Python monorepo of **strictly-separated** modules that improve the generation and
humanization steps. Additive — it does **not** replace the live n8n pipeline yet;
each module maps to one step of the agreed sequence and only `common/` is shared.

## Modules (import order = pipeline order)

| Module | Step | What it does | LLM? |
|---|---|---|---|
| `voice_guard` | 1 | Builds the system prompt — author **voice parameters** + **all guardrails** + **master info file** + **Guardian of Truth**, hardcoded — and drives generation **one section at a time (300–600 words)** instead of the whole article at once. | drives it (injected) |
| `macro_guardrail` | 2 | Section-level structural gate. Reduces a section to a **structured byte string of paragraph token-lengths + sentence-counts** (no vocabulary), then uses **gzip Normalized Compression Distance (NCD)** vs a uniform baseline. Low NCD = robotic/low-entropy block pattern → **reject** and trigger an LLM rewrite loop (`max_retries=3`). No sentence/word logic. | no (caller's rewrite is) |
| `micro_guardrail` | 3 | Computes the **Coefficient of Variation (CV)** of sentence lengths. If too uniform, **algorithmically splits a long / combines two short** sentences to raise micro-burstiness. **Never changes the paragraph count or breaks** established in Step 1. | no |
| `lexical_injector` | 5 | **Absolute end.** (a) JSON loader of high-BCP words by `destination`/`activity`/`feeling`; (b) POS-tags text and swaps generic high-probability adjectives/verbs for mapped low-probability ones; (c) splices a **verbatim human sentence** into a paragraph's middle as a perplexity **"salt"**. Runs last so nothing overwrites the injected tokens. | no |
| `orchestrator` | — | Wires 1→2→3, assembles the article, runs the **humanization** pass then **re-runs macro + micro** to verify structural integrity, then `lexical_injector` last. All effects (generate/rewrite/humanize) are injected callables. | injected |
| `common` | — | Tokenizer/POS interface. Backend = **nltk** (spaCy has no wheels on Python 3.14 yet; swap it in here). | no |

## Setup & test
```bash
python3 -m venv .venv-pipeline && . .venv-pipeline/bin/activate
pip install -e content-pipeline           # or: pip install nltk
PYTHONPATH=content-pipeline python content-pipeline/tests/test_pipeline.py   # 6/6
```

## Live wiring (deterministic modules, no LLM)
The macro/micro/lexical modules are exposed as an HTTP service the n8n pipeline can
call (like the pattern-breaker workflow):
```bash
pip install -e 'content-pipeline[service]'
uvicorn content_pipeline.service.app:app --host 0.0.0.0 --port 8080
```
Endpoints: `POST /macro/evaluate`, `/micro/enforce`, `/verify` (humanization-step
macro+micro), `/lexical/inject`. **Needs a Python host** — n8n Cloud can't run Python
in a code node, so this service must be deployed somewhere n8n can reach, then wired
into the humanize / post-humanize stages. That hosting/wiring is the remaining step.

## Notes
- Deterministic: gzip, hashing and fixed rules — same input → same output, no model.
- `data/lexicon.json` is a **seed** database; expand `generic_replacements`,
  `categories`, and `human_sentences` over time.
- Thresholds are constants at the top of each module (`DEFAULT_NCD_MIN`,
  `DEFAULT_CV_MIN`) — calibrate against the real corpus.
