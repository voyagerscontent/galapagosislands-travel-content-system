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
├── dictionary/          # 5 hardcoded JSON files (~1,555 rules)
│   ├── core_words.json
│   ├── core_phrases.json
│   ├── travel_words.json
│   ├── travel_phrases.json
│   └── travel_variants.json  # NEW v1.1 — array values w/ Markov picker
├── humanizer/           # Python engine (regex, no LLM)
│   ├── engine.py        # Humanizer + HumanizeResult
│   ├── cli.py           # command-line tool
│   └── api.py           # optional Flask API
├── intake/              # 3000-word browser intake page (offline capable)
│   ├─�� index.html
│   ├── build_intake.py
│   └── dictionary.bundle.js   (generated)
├── n8n/                 # n8n workflow JSON files (Code node + Set-node chain)
│   └── build_n8n_workflow.py
├── skill/SKILL.md       # portable skill definition
├── tests/               # pytest suite
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

- **Deterministic** — every run identical, offline, hardcoded.
- **Case-preserving** — `DELVE` → `LOOK AT`, `Delve` → `Look at`.
- **Word-boundary safe** — `predelved` untouched.
- **Phrase-first, longest-first** — no partial-match collisions.
- **3,000-word cap** per submission.
- **Non-patterned variants** — when an AI phrase has multiple human alternatives
  (e.g. *the enchanted islands* → *the Galapagos* / *the archipelago* /
  *the islands* / *the Galapagos archipelago*), a first-order Markov walker
  picks a different variant every time the phrase reappears in the same text.
  The walk is **seeded by the input + optional user seed**, so the choice is
  fully deterministic yet the output no longer reads like a stuck record.

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
