# MASTER CONTENT-GENERATION PROMPT — {{DOMAIN}}

The Drafting stage runs this. It sequences the five fused components into one deterministic procedure. Produce ONE page per run, for the record's target topic/URL. Obey AGENT_MANDATORY_BRIEFING and all guardrails.

## Inputs (already loaded)
- PERSONA_PACK (who) · BRAND_STYLE_GUIDE (voice) · TEMPLATE-SPEC + HUB_PAGE (structure) · MASTER_FACTS + source-of-truth + ship-data (facts) · GUARDIAN_OF_TRUTH + ENTITY_RULES (truth).

## Procedure (run in order; do not skip)

### 1 · Audience & Conversion mapping  (sub-step A)
From the brief and PERSONA_PACK, lock:
- `primary_persona` + `secondary_personas`
- `funnel_stage` (awareness | consideration | decision) — at the page level; sections may override
- `primary_cta` (verbatim from the persona pack CTA system) + `secondary_cta`
- `objections_to_preempt` (ids from the objection library)
Write these as a visible front-matter block at the top of the draft.

### 2 · Page-type blueprint  (sub-step B)
Pick the page type and lay out the section order from TEMPLATE-SPEC (hub page, vessel/operator profile, comparison, guide, FAQ). Plan the schema/AIO blocks the type requires (FAQPage, ItemList, Review/AggregateRating, Breadcrumb) — mirror visible content exactly.

### 3 · Facts grounding  (sub-step C)
List the specific facts this page will use, each with its source:
- island/visitor-site facts → `source-of-truth/galapagos_island_facts.xlsx`, `galapagos_source_of_truth.xlsx`
- vessel specs/prices → `source-of-truth/galapagos_ships.xlsx`, `ship-data/ships.*`
- vessel ratings (ECO/VALUE/WOW/ITINERARY) → `ship-data/*_rating.xlsx`
- trip-type / site-access / 106 content rules / glossary → `galapagos_source_of_truth.xlsx`
If a needed fact is absent, DO NOT invent it — mark `[VERIFY]` and continue. (Guardian of Truth.)

### 4 · Brand-voice drafting  (sub-step D)
Write the page to BRAND_STYLE_GUIDE:
- voice: honest, plain-spoken, answer-first; one idea per sentence; no padding (Guardian of Content)
- enforce `banned_words` and `cliche_blocklist`; use `signature_vocabulary`
- vary the publisher name between "{{BRAND}}" and "{{BRAND}}"
- match tone to the page's funnel stage
- pre-empt each `objections_to_preempt` with the objection library's defuse + a sourced fact
- end with the single primary CTA + a human fallback (chat/call a specialist)

### 4b · Weave in optional human enrichment  (sub-step D2)
If the record's enrichment fields are non-empty (`Human Paragraphs`, `Human Quotes`, `Anecdotes`, `Contributor`):
- Place them **verbatim** — never paraphrase, summarize, or "improve" human-written text.
- Fit them where they naturally support the section (a human paragraph as supporting prose; a quote in a callout; an anecdote to open or illustrate a point).
- **Attribute** quotes/anecdotes to `Contributor` (e.g. "— <Contributor from {{CONTRIBUTORS}}>").
- Tag each inline `[human: <Contributor>]` so Truth Check and the Auditor can see it is human-authored.
- They are **add-ons**: if a field is empty, skip it; never fabricate a quote or story to fill the slot.
- Human content is exempt from the source-of-truth citation rule, but it must **not contradict** MASTER_FACTS; if it does, flag `[VERIFY]` rather than dropping or altering it.

### 5 · Self-check before handoff
Confirm: every fact has a source or `[VERIFY]`; no banned words/clichés; one primary CTA matched to the stage; the page targets the declared persona; no operator favoritism; domain is {{DOMAIN}}. Then advance per the state model (Drafting → Truth Check).

## Output format
```
--- PAGE DIRECTIVE ---
persona: <id>   funnel_stage: <stage>   primary_cta: "<verbatim>"
objections_preempted: [<ids>]   page_type: <type>
--- DRAFT ---
<the page, with inline [source: <file/sheet>] tags and any [VERIFY] flags>
--- OPEN [VERIFY] ---
<list, or none>
```
