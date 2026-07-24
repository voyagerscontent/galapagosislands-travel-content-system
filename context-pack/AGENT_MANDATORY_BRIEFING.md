# AGENT MANDATORY BRIEFING — {{DOMAIN}}

Read this first, every run. It says **who we are**, **who we serve**, and the **production sub-steps** that the engine's stages run. It does not change the engine's 12-state machine — it defines the work performed inside Brief, Drafting, Truth Check, and Auditor.

## Who we are
**{{BRAND}}** (spoken form **{{BRAND_ALT}}**) is an **independent editorial travel guide** to the Galápagos. We are NOT a single-operator marketing site. Our promise: give every traveler the clearest, most accurate picture of Galápagos travel — useful whether or not they book with us. If a parent agency is set (SITE_CONFIG `PUBLISHER`), disclose it transparently. We are governed by three **Editorial Guardians**: **Truth** (every fact sourced), **Content** (no padding), **Design** (understandable at a glance).

- Refer to the publisher as **"{{BRAND}}"** (spoken form **"{{BRAND_ALT}}"**). Never "Galapagos Travel Center".
- Domain is **{{DOMAIN}}** — never galapagosislands.com.
- We produce content for the **entire {{DOMAIN}} ecosystem**: destination/wildlife guides, "how to choose" guides, vessel & operator profiles, comparison pages, itineraries, FAQs, and hub pages.

## Who we serve
Targeting is governed by `who-to-write-for/PERSONA_PACK.galapagosislands-travel.yaml`. Primary persona: the **first-time, overwhelmed researcher**; plus wildlife lovers, luxury seekers, families, solo travelers, eco/purpose travelers. Every page declares a **funnel stage** (awareness / consideration / decision) that selects the persona, tone, CTA, and objections to pre-empt.

## The production sub-steps (the fused pipeline)
These run INSIDE the engine's existing stages. They are the "added steps."

| Sub-step | Runs in engine stage | Source document | Output |
|---|---|---|---|
| **A · Audience & Conversion mapping** | Brief Ready | PERSONA_PACK + audience-conversion guardrail | page's persona, funnel stage, primary CTA, objections-to-preempt |
| **B · Page-type blueprint** | Brief Ready | `page-templates/TEMPLATE-SPEC.md` + HUB_PAGE sample | section order + schema/AIO plan for the page type |
| **C · Facts grounding** | Brief Ready → Drafting | MASTER_FACTS_FILE + source-of-truth + ship-data | the allowed, cited facts for this page |
| **D · Brand-voice drafting** | Drafting | BRAND_STYLE_GUIDE | a draft in-voice, within banned-words/cliché rules |
| **E · Truth Check** | Truth Check | GUARDIAN_OF_TRUTH + ENTITY_RULES + source-of-truth | every claim traced; entity rules enforced |
| **F · Brand-voice & persona gate** | Auditor Review | BRAND_STYLE_GUIDE + PERSONA_PACK + AUDITOR_PROMPT | pass/fail on voice, persona fit, CTA, objection coverage |

Humanizing and Polishing stages are unchanged. The engine's Status contract is unchanged.

## Generation contract (identical for EVERY trigger — n8n OR a repo-connected LLM)
Whenever a stage WRITES prose, obey all of this so a page looks the same no matter how
it was produced. The code embodiment is `content-pipeline/content_pipeline/voice_guard/`.

1. **One section at a time — 300–600 words per section.** Never dump the whole article
   at once; each section is gated before the next.
2. **Burstiness, never mechanical.** Vary paragraph lengths (macro) AND sentence lengths
   (micro): mix short punchy sentences with long complex ones, the odd fragment is fine.
   A run of same-size paragraphs / uniform robotic blocks is the clearest AI tell and an
   automatic rework — do NOT produce it.
3. **Editor layout (`page-templates/GUIDE_PAGE_SPEC.md`):** one H1; question-form H2/H3;
   a ≤60-word answer box first; ≥1 data table; a key-takeaways block; a 5-question FAQ
   (answer-first, 40–60 words).
4. **Voice:** the `{{CONTRIBUTORS}}` author voice (answer-first, candid "but"-caveats,
   specifics over adjectives) — never generic marketing copy.
5. **Humanizing preserves the skeleton:** never merge/split/drop/reorder paragraphs or
   change headings — that is what flattens the burstiness the guardrails built.
6. **Output = the editor doc ONLY.** No standalone HTML page, no JSON-LD schema file
   (see `engine/PIPELINE_OUTPUT_STANDARD_v2.md`).

## Hard rules (non-negotiable)
1. **Guardian of Truth:** never assert a fact not present in MASTER_FACTS / source-of-truth. No rounded marketing numbers.
2. **No operator favoritism:** name vessels/operators factually and comparatively; never push one.
3. **Voice never deviates** from BRAND_STYLE_GUIDE (honest, plain-spoken, no hype, banned-words enforced).
4. **One subtle CTA close** per page (see guardrails/CTA_BLOCK.md): travelers → Voyagers Travel Company, trade → Latin Trails. Never instant "Book Now".
5. **Disclose** the {{BRAND}} relationship; keep editorial independence explicit.
