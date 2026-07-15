# Install into a Perplexity Space — {{DOMAIN}}

This project ships the **engine** (loop-free state machine, unchanged) plus the **context pack** that adapts content production to the entire `{{DOMAIN}}` ecosystem. Drop it into its own Perplexity Space; the same engine can serve other sites by cloning the project and swapping the context pack.

## Step 1 — engine (custom instructions + state)
1. Set the Space **custom instructions** to `engine/02_ORCHESTRATOR_PERPLEXITY.md`.
2. Upload `engine/01_PIPELINE_STATUS_MODEL.md` and `config/SITE_CONFIG.md` as Space files.
3. Keep `engine/automation`-side files (`airtable_schema.json`, `build_airtable_base.py`, `n8n_pipeline_corrected.json`) and `engine/UPLOAD_TO_PERPLEXITY.md` for the n8n + Airtable setup.

## Step 2 — upload the context pack (the per-site brain)
Upload these as Space files so the orchestrator can load them once per run:

**Who to write for**
- `context-pack/who-to-write-for/PERSONA_PACK.galapagosislands-travel.yaml`
- `context-pack/who-to-write-for/audience-conversion-guardrail.template.yaml`

**Brand voice**
- `context-pack/brand-voice/BRAND_STYLE_GUIDE.galapagosislands-travel.yaml`

**What to write about**
- `context-pack/AGENT_MANDATORY_BRIEFING.md`  (who we are + the production sub-steps)
- `context-pack/MASTER_FACTS_FILE.md`  (grounding facts + pointers to the data)
- `context-pack/CONTENT_GENERATION_PROMPT.md`  (the master prompt that sequences the 5 components)
- `context-pack/what-to-write-about/page-templates/TEMPLATE-SPEC.md` (+ the HUB_PAGE sample/template/styles)
- the source-of-truth + ship-data workbooks under `context-pack/what-to-write-about/` (attach as reference data)

**Guardrails (loaded every run; Auditor file only at the Auditor stage)**
- `context-pack/guardrails/GUARDIAN_OF_TRUTH.md`
- `context-pack/guardrails/CONTENT_FIDELITY.md`
- `context-pack/guardrails/ENTITY_RULES.md`
- `context-pack/guardrails/AUDITOR_PROMPT.md`

## Step 3 — Airtable + n8n
- Create a NEW Airtable base for {{DOMAIN}}; apply `engine/airtable_schema.json` `Status` options exactly, add the guard fields (`Attempt Count`, `Return To`, `Last Error`, the `*_Link` fields) plus the context fields (`Persona`, `Funnel Stage`, `Primary CTA`) and the intake + human-enrichment fields from `interface/airtable_intake_fields.json`.
- Import `engine/n8n_pipeline_corrected.json`; clone the node group per stage; set the `airtable_credential_name` from SITE_CONFIG.

## Step 4 — team intake (activate-by-adding-data)
Follow `interface/AIRTABLE_INTAKE_FORM.md`: either publish an Airtable **Form view** (no hosting) or host `interface/intake-form.html` pointed at an n8n intake webhook. Submitting creates a `Backlog` record and the pipeline runs. Optional human enrichment (paragraphs/quotes/anecdotes) flows to Drafting sub-step 4b and is preserved verbatim.

## Before go-live
Run `python engine/validate_pipeline.py` -> must print `ALL CHECKS PASSED`. It confirms the `Status` strings line up across Airtable, n8n, and the orchestrator (the thing that prevents loops). The engine is unchanged, so this passes as on the reference site.

## The load order the orchestrator expects (once per run)
1. `engine/02_ORCHESTRATOR_PERPLEXITY.md` (instructions)
2. `context-pack/AGENT_MANDATORY_BRIEFING.md`
3. `context-pack/guardrails/GUARDIAN_OF_TRUTH.md`
4. `context-pack/guardrails/CONTENT_FIDELITY.md`
5. `context-pack/guardrails/ENTITY_RULES.md`
6. `context-pack/MASTER_FACTS_FILE.md`
7. `context-pack/who-to-write-for/PERSONA_PACK.galapagosislands-travel.yaml`
8. `context-pack/brand-voice/BRAND_STYLE_GUIDE.galapagosislands-travel.yaml`
9. `context-pack/CONTENT_GENERATION_PROMPT.md`
10. `engine/01_PIPELINE_STATUS_MODEL.md`
11. `context-pack/guardrails/AUDITOR_PROMPT.md` (only at the Auditor stage)
