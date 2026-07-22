---
name: human-dictionary-travel
description: Deterministic AI-quirk → plain-English rewriter for travel copy. Use when the user asks to humanize, de-GPT, or clean AI-sounding travel content (Colombia, Ecuador, Peru, Bolivia, Brazil, Chile, Argentina, Patagonia, Galapagos, Amazon, Antarctica, Arctic; expedition cruises, nature/culture/adventure tours, lodges, luxury/custom travel, Voyagers). Hardcoded regex — no LLM.
version: 1.0.0
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

## Guarantees

- **No LLM.** All replacements are regex-based against JSON dictionaries in `dictionary/`.
- **Deterministic.** No randomness, no temperature, no rate limits.
- **Case-preserving.** `DELVE`→`LOOK AT`, `Delve`→`Look at`, `delve`→`look at`.
- **Word-boundary safe.** `predelved` is left alone.
- **Phrase-first, longest-first.** `"embark on a journey of a lifetime"` matches before `"embark"`.
- **Hard 3,000-word cap** per submission (configurable).

## Dictionaries (in apply order)

| File | Scope | Notes |
|---|---|---|
| `dictionary/travel_phrases.json` | Travel phrases + brand | Most specific; applied first |
| `dictionary/core_phrases.json` | Universal AI phrases | e.g. "delve into", "in today's digital age" |
| `dictionary/travel_words.json` | Travel words + brand | e.g. "picturesque", "unforgettable", "immerse" |
| `dictionary/core_words.json` | Universal AI words | e.g. "delve", "leverage", "tapestry" |

Total: **~1,170 rules**.

## Python usage

```python
from humanizer import Humanizer

h = Humanizer()   # loads all four JSON dictionaries
result = h.humanize(
    "Embark on a journey of a lifetime as you delve into the enchanted islands "
    "of the Galapagos."
)

print(result.text)
# -> "Start a top trip as you look at the Galapagos."

for r in result.replacements:
    print(r.original, "→", r.replacement, "(", r.source, ")")
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

## n8n workflow

Import `n8n/n8n_workflow_code_node.json` into n8n. It exposes a
`POST /webhook/humanize` endpoint that runs the same ruleset in a Code node.

Rebuild after dictionary changes:

```bash
python n8n/build_n8n_workflow.py
```

## Extending the dictionary

1. Add entries to the right JSON file (phrases beat words; travel beats core).
2. Prefer **plain, specific** replacements over synonyms.
3. Keep the brand name **Voyagers** capitalized in output values.
4. Rebuild the intake bundle and the n8n workflow.
5. Run tests: `pytest tests/`.

## Non-goals

- This does **not** paraphrase, restructure, or fact-check.
- It will not fix grammar or sentence flow beyond punctuation cleanup.
- Combine with a human editor for the final pass.
