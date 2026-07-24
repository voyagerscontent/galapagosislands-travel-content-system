---
name: human-dictionary-travel
description: Deterministic AI-quirk → plain-English rewriter for travel copy. Use when the user asks to humanize, de-GPT, or clean AI-sounding travel content (Colombia, Ecuador, Peru, Bolivia, Brazil, Chile, Argentina, Patagonia, Galapagos, Amazon, Antarctica, Arctic; expedition cruises, nature/culture/adventure tours, lodges, luxury/custom travel, Voyagers). Two-pass architecture — hardcoded regex + Markov variants (no LLM), plus a context-trigger flag layer for AI structural patterns that need sentence-level rewrite via a strictly guarded OpenAI call.
version: 1.4.0
---

# human-dictionary-travel

Hardcoded, deterministic word/phrase replacement for travel copy. Zero LLM
dependency. Same input always produces the same output.

## When to use

Load this skill when the user wants to:

- Remove AI writing tells from travel copy (blog posts, itineraries, landing pages, emails).
- Enforce a plain-English house style across marketing content for Voyagers,
  Latin Trails, galapagosislands.travel, selectotravel.com, and related sites.
- Batch-process copy inside an n8n workflow with no LLM calls.

## Architecture (v1.4)

Two passes:

1. **Regex + Markov layer** — hardcoded JSON dictionaries. No LLM.
   Deterministic character-for-character.
2. **Context-trigger flag layer** — 21 regexes for AI structural patterns
   (whole-sentence tropes) that cannot be cleanly substituted. The engine
   FLAGS these matches but does NOT modify text. A downstream OpenAI call
   in n8n (or optionally in the intake page) rewrites the flagged sentence,
   with a **verbatim guardrail** that discards the rewrite unless it
   contains one of the pre-approved `human_variants` character-for-character.

## Guarantees

- **No LLM in the Python engine.** The engine stays 100% offline.
- **Deterministic regex + Markov pass.** No randomness, no temperature.
- **Case-preserving.** `DELVE`→`LOOK AT`, `Delve`→`Look at`, `delve`→`look at`.
- **Word-boundary safe.** `predelved` is left alone.
- **Phrase-first, longest-first.** `"embark on a journey of a lifetime"` matches before `"embark"`.
- **Hard 3,000-word cap** per submission (configurable).
- **Verbatim LLM guardrail.** When the context-trigger layer is fed to
  OpenAI downstream, the LLM output MUST contain a pre-approved variant
  character-for-character; otherwise the flagged text is kept as-is. The
  LLM cannot invent new phrasing that reintroduces AI quirks.

## Dictionaries (in apply order)

| File | Scope | Notes |
|---|---|---|
| `dictionary/travel_variants.json` | Travel phrases w/ multiple variants | v1.1 — Markov-picked |
| `dictionary/travel_phrases.json` | Travel phrases + brand | Single-value replacements |
| `dictionary/core_phrases.json` | Universal AI phrases | e.g. "delve into", "in today's digital age" |
| `dictionary/travel_words.json` | Travel words + brand | e.g. "picturesque", "unforgettable", "immerse" |
| `dictionary/core_words.json` | Universal AI words | e.g. "delve", "leverage", "tapestry" |
| `dictionary/travel_context_triggers.json` | AI structural patterns | v1.4 — FLAGGED, not substituted; 21 triggers, 253 variants |

Total: **~1,569 regex rules + 21 context triggers**.

## Python usage

```python
from humanizer import Humanizer

h = Humanizer()   # loads all dictionaries + context triggers
result = h.humanize(
    "Embark on a journey of a lifetime as you delve into the enchanted islands "
    "of the Galapagos. Whether you're a family or a solo traveler, there is "
    "something for everyone."
)

print(result.text)                # deterministic regex-swapped text
print(result.replacement_count)   # e.g. 4
print(result.flag_count)          # e.g. 1 (whether-something-for-everyone flagged)

for r in result.replacements:
    print(r.original, "→", r.replacement, "(", r.source, ")")

for s in result.flagged_spans:
    print(s.trigger_id, "::", s.matched_text)
    print("  candidates:", s.candidate_variants[:3])
    print("  instruction:", s.llm_instruction)
```

## CLI

```bash
echo "Delve into Patagonia" | python -m humanizer.cli
python -m humanizer.cli --input draft.md --output humanized.md --json report.json
```

## Local API + intake page

```bash
pip install flask flask-cors
python -m humanizer.api            # http://localhost:8787
# GET  /health   /rules   POST /humanize {"text": "..."}
```

Or open `intake/index.html` directly — the compiled bundle runs client-side.

Rebuild the JS bundle after editing dictionaries:

```bash
python intake/build_intake.py
```

## n8n workflows

Two files shipped:

- `n8n/n8n_workflow_code_node.json` — deterministic only. Regex + Markov +
  flag emission, no LLM. `POST /webhook/humanize` returns
  `{ text, replacements, flagged_spans, ... }`.
- `n8n/n8n_workflow_with_openai.json` — two-pass with OpenAI. Runs the
  deterministic pass, splits flagged spans out, calls OpenAI
  (`gpt-4o-mini`, `temperature=0`, `seed=42`) via an HTTP Request node,
  validates the verbatim guardrail in a Code node, aggregates the accepted
  rewrites, and reassembles the final text. Requires an `openAiApi`
  credential in n8n.

Rebuild after dictionary or trigger changes:

```bash
python n8n/build_n8n_workflow.py
```

## Extending the dictionary

1. Add entries to the right JSON file (phrases beat words; travel beats core).
2. Prefer **plain, specific** replacements over synonyms.
3. Keep the brand name **Voyagers** capitalized in output values.
4. For context triggers, keep `human_variants` short (≤ 20 words each),
   attested by `human_corpus.json` where possible, and tagged with
   `source: corpus` or `source: curated`.
5. Rebuild the intake bundle and the n8n workflow.
6. Run tests: `pytest tests/` (31 tests must pass).

## Non-goals

- This does **not** paraphrase, restructure, or fact-check.
- It will not fix grammar or sentence flow beyond punctuation cleanup.
- Combine with a human editor for the final pass.
