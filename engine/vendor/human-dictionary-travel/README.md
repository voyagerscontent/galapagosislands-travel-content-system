# human-dictionary-travel

**Deterministic AI-quirk → plain-English rewriter for travel copy.**
Zero LLM. Zero network. Same input → same output, always.

Built for the Voyagers / Latin Trails / galapagosislands.travel content pipeline
covering Colombia, Ecuador, Peru, Bolivia, Brazil, Chile, Argentina, Patagonia,
the Galapagos, the Amazon, Antarctica, and the Arctic — across expedition
cruises, nature tours, cultural immersion, overland trips, lodges, luxury and
custom travel.

> Inspired by the word-frequency dictionary approach of
> [`company-wordfreq.el`](https://github.com/johannes-mueller/company-wordfreq.el):
> put the source of truth in a plain text/JSON file, keep the runtime dumb.

## What's inside

```
human-dictionary-travel/
├── dictionary/          # 6 hardcoded JSON files (~1,569 rules + 21 triggers)
│   ├── core_words.json
│   ├── core_phrases.json
│   ├── travel_words.json
│   ├── travel_phrases.json
│   ├── travel_variants.json         # v1.1 — array values w/ Markov picker
│   ├── human_corpus.json            # v1.2 — 2,307 real forum sentences (reference)
│   └── travel_context_triggers.json # v1.4 — 21 context-trigger regexes, 253 variants
├── humanizer/           # Python engine (regex + flagger, no LLM)
│   ├── engine.py        # Humanizer + HumanizeResult + FlaggedSpan
│   ├── cli.py           # command-line tool
│   └── api.py           # optional Flask API
├── intake/              # 3000-word browser intake page (offline capable)
│   ├── index.html                   # v1.4 — shows flagged spans + optional LLM rewrite
│   ├── build_intake.py
│   └── dictionary.bundle.js         (generated)
├── n8n/                 # n8n workflow JSONs
│   ├── build_n8n_workflow.py
│   ├── n8n_workflow_code_node.json     # deterministic only (regex + flag)
│   ├── n8n_workflow_with_openai.json   # v1.4 — two-pass with OpenAI HTTP node
│   └── n8n_workflow_regex_chain.json   # illustrative Set-node chain
├── skill/SKILL.md       # portable skill definition
├── tests/               # pytest suite (31 tests)
└── examples/
```

## Quick start

```bash
# 1. run tests
pytest tests/

# 2. humanize from CLI
echo "Embark on a journey to delve into the Amazon." | python -m humanizer.cli

# 3. rebuild the intake page bundle
python intake/build_intake.py
open intake/index.html

# 4. rebuild the n8n workflow
python n8n/build_n8n_workflow.py
# import n8n/n8n_workflow_code_node.json into n8n
```

## Example

Input:

> Embark on a journey of a lifetime as you delve into the enchanted islands of the Galapagos. Our expertly crafted itinerary invites the discerning traveler to immerse themselves in nature's most vibrant tapestry, where iconic wildlife and pristine landscapes converge in a truly unforgettable experience. Nestled in the heart of Patagonia, our boutique expedition vessel offers world-class hospitality alongside meticulously planned shore excursions. At Voyagers, we believe travel is more than just a vacation — it's a transformative journey that will leave you spellbound.

Output:

> Start a top trip as you look at the Galapagos. Our planned itinerary invites the discerning traveler to experience nature's most lively mix, where well-known animals and clean landscapes converge in a truly trip you'll remember. Set deep in Patagonia, our small expedition ship offers top hospitality alongside carefully planned shore trips. At Voyagers, we believe travel is more than a vacation — it's a big trip that will amaze you.

## Guarantees

- **Deterministic regex pass** — every run identical, offline, hardcoded.
- **Case-preserving** — `DELVE` → `LOOK AT`, `Delve` → `Look at`.
- **Word-boundary safe** — `predelved` untouched.
- **Phrase-first, longest-first** — no partial-match collisions.
- **3,000-word cap** per submission.
- **Non-patterned variants** — when an AI phrase has multiple human alternatives,
  a first-order Markov walker picks a different variant every time the phrase
  reappears. The walk is seeded by the input + optional user seed, so it's
  fully deterministic yet non-repeating.
- **Verbatim LLM guardrail (v1.4)** — when the context-trigger layer flags
  an AI structural pattern, the downstream OpenAI call must include one of
  the pre-approved `human_variants` character-for-character. If it doesn't,
  the flagged text is left unchanged. LLM cannot invent new phrasing that
  reintroduces AI quirks.

## Variant dictionary (v1.1)

`travel_variants.json` is the same shape as the other dictionaries, except
values are **arrays**:

```json
{
  "replacements": {
    "the enchanted islands": [
      "the Galapagos",
      "the Galapagos archipelago",
      "the islands",
      "the archipelago"
    ]
  }
}
```

All runtimes (Python engine, browser intake page, n8n Code node) share the
same FNV-1a-based hash and Markov state machine, so a given input yields
the same output in every environment.

## Context-trigger layer (v1.4)

`dictionary/travel_context_triggers.json` defines 21 AI structural patterns
that can't be cleanly regex-swapped — whole-sentence tropes like
*"Whether you're X or Y, there is something for everyone"* or *"Our expert
team will curate the perfect itinerary."*

Each trigger has:

- `trigger_pattern` — Python regex (JS-portable; inline `(?i)`/`(?is)`
  flags are stripped and remapped by consumers).
- `topic_bucket`, `reason`, `instruction_to_llm`.
- `human_variants` — 253 total, 6–16 per trigger, each tagged
  `{"text": ..., "source": "corpus" | "curated"}`.

**The Python engine does NOT substitute for these matches.** It emits
`flagged_spans` on `HumanizeResult` with the matched text, char range,
local context, an ordered candidate list of variants, and the LLM
instruction. Downstream consumers call OpenAI with a strict verbatim
guardrail.

**Two n8n workflows shipped:**

- `n8n_workflow_code_node.json` — deterministic only. Emits `flagged_spans`
  for external processing but performs no LLM rewrite.
- `n8n_workflow_with_openai.json` — two-pass. Runs the deterministic pass,
  splits flagged spans out, calls OpenAI (`gpt-4o-mini`, `temperature=0`,
  `seed=42`), validates the verbatim guardrail in a Code node, then
  reassembles the final text. Requires an `openAiApi` credential in n8n.

**The intake page** shows flagged spans as inline highlights with hover
tooltips listing approved variants. LLM rewrite is optional — paste an
OpenAI API key (stays in your browser only) and click "Rewrite flagged"
to call OpenAI directly with the same guardrail.

## Human corpus (v1.2)

`dictionary/human_corpus.json` is a **reference-only** file containing 2,307
authentic human sentences collected from TripAdvisor forums and expedition
cruise communities (Galapagos, Amazon, Antarctica, Peru, Falklands, Cruise
Critic, small-ship-cruising subreddit, etc.).

It is **not** loaded by the engine — these are full sentences, not
grammatical drop-in replacements for AI noun-phrases. It exists so
maintainers can:

1. Validate that noun-phrase variants in `travel_variants.json` reflect
   how real travelers actually talk. (v1.2 pulled 11 additional
   corpus-attested variants: "the Antarctic", "the continent",
   "the Galapagos Islands", "the Amazon river", "Peru", etc.)
2. Search the corpus by topic bucket (`galapagos`, `cruise`, `antarctica`,
   `amazon`, `peru`, `ecuador`, `planning`, `wildlife`, `weather`,
   `health`) when adding future variants.
3. Grep for specific concepts before inventing new AI-trigger keys.

Source file: `master_travel_phrases.xlsx`.

## Use as a portable skill

Copy `skill/SKILL.md` (plus the `dictionary/` and `humanizer/` folders) into any
downstream repo. Load via your skills index by folder name.

## Extending the dictionary

Add entries to the appropriate JSON file, then:

```bash
python intake/build_intake.py         # refresh browser bundle
python n8n/build_n8n_workflow.py      # refresh n8n workflow
pytest tests/                         # sanity check
```

Ordering rules:

1. **Phrases beat words.** If a phrase form exists, add it there.
2. **Travel beats core.** Domain-specific dictionaries apply first.
3. **Longer beats shorter.** Automatic — engine sorts by length descending.
4. **Preserve brand casing.** Keep `Voyagers` capitalized in output values.

## License

MIT. Dictionaries derived from public overuse-word compilations
(GPTZero, blader/humanizer, lguz/humanize-writing-skill, community lists) and
customized for Voyagers travel-domain copy.
