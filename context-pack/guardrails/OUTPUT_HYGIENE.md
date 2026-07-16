# OUTPUT HYGIENE — {{DOMAIN}}

The rules are not the content. Everything the engine loads — the briefing, the guardrails,
the hard truths, the templates, this file — tells you what you MAY and MAY NOT write.
None of it is material to write ABOUT. Obey it silently.

Applies at every stage. Enforced hard at **Auditor Review** (Part H).

## 1 · Never recite a rule as a sentence

A page must never talk about its own editorial stance. These have all shipped and are banned:

- "an honest trade-off, not a ranking"
- "with no operator favoritism"
- "an independent editorial guide" (as body copy — the positioning is *practised*, not announced)
- "Luxury is the boat, not the map"
- "we don't play favorites"

If a sentence's real subject is your own rules or process, cut it. Readers came for the answer.

## 2 · HARD TRUTHS are prohibitions, not paragraphs

HT-1 and HT-2 (see GUARDIAN_OF_TRUTH) constrain what you may claim. They are honoured by
**not making the banned claim** — never by announcing the rule:

| Honour it by | Not by |
|---|---|
| Never calling a month "best" without saying what for | "The Galápagos is a year-round destination" |
| Never implying islands visited make a boat luxurious | "No island is better than another" |

Write about timing or luxury **only when the page's topic is timing or luxury**. A land-iguana
facts page needs neither. When a hard truth IS on-topic — HT-2 on a cost page, where what money
buys is the subject — render it as reader guidance, not a recital.

## 3 · Internal markers never reach a reader

`[source: …]`, `[VERIFY]` and `[human: …]` are **internal**. They exist so Truth Check and the
Auditor can trace grounding. They are not reader-facing citations and not a house style.

They are REQUIRED at draft and FORBIDDEN at publication. Which applies depends on the stage
you are running — your stage prompt states it. **Never judge an artifact by another stage's
standard.**

| Stage | Markers |
|---|---|
| Drafting, Truth Check, Humanizing | REQUIRED — internal artifacts, no reader sees them |
| Polishing onward | FORBIDDEN — one surviving marker is a defect |

**Polishing** is the publication boundary and owns the conversion:
- Strip every marker from body, tables, FAQ and JSON-LD.
- Replace with prose attribution **only where the fact is notable, surprising or contested**
  ("the Charles Darwin Foundation records about 350"), and close with a short `Sources` line
  naming the bodies used. Most sentences need no attribution — a footnoted term paper is not
  a travel guide.
- Resolve or cut every `[VERIFY]`. It must never be published.
- `[human: …]` tags are stripped, but the human text itself stays **verbatim** and keeps its
  visible attribution to the Contributor (see CONTENT_GENERATION_PROMPT D2).

## 4 · No meta-commentary

Nothing about the page, the brand's independence, the pipeline, or your process.

## 5 · Grounding markers are a fixed set

`[source: <file/sheet>]` per GUARDIAN_OF_TRUTH rule 1. Do not invent marker vocabularies
(`[HT-2]`, `[MASTER FACTS]`, bare `[GC]`/`[CDF]` provenance codes lifted out of the facts
files). Those codes exist *inside* the source data as its own provenance; they are not an
output convention.

## Auditor check (Part H — hard fail)

1. Zero `[source:`, `[VERIFY]`, `[human:`, `[HT-`, `[GC]`, `[GCT]`, `[CDF]`, `[DPNG]`,
   `[MASTER FACTS]` anywhere in the polished page, **including inside JSON-LD**.
2. No guardrail recited as copy (§1), and no stock HT-1/HT-2 paragraph on a page whose topic
   is neither timing nor luxury (§2).

Quote the offending text for every failure.
