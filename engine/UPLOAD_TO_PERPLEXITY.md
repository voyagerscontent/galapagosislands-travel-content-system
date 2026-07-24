# Upload to a Perplexity Space — two steps

This zip is the **pipeline engine only** — the loop-free state machine, orchestrator, Airtable schema, and n8n workflow. It contains **no** site rules, facts, personas, or briefs. That is intentional: the engine is website-agnostic, and your context files are uploaded separately so the same engine can serve any site.

## Step 1 — upload this package
Create (or open) your Perplexity Space and upload the contents of this zip:
- Set the Space **custom instructions** to `02_ORCHESTRATOR_PERPLEXITY.md`.
- Upload `01_PIPELINE_STATUS_MODEL.md` and `config/SITE_CONFIG.md` as Space files.
- Keep `automation/` and `validate_pipeline.py` for the n8n + Airtable side.

## Step 2 — upload your context files
After the engine is in place, upload your existing context/rule files to the same Space — the ones that tell it **who to write for** and **what to write about**:
- *Who to write for:* `AGENT_MANDATORY_BRIEFING.md`, the two `reader-persona-*` files, `MARCEL_PERKINS_VOICE_FINGERPRINT`.
- *What to write about:* `context-pack/MASTER_FACTS_FILE.md`, `context-pack/CONTENT_GENERATION_PROMPT.md`, the page briefs.
- *Guardrails:* Guardian of Truth, Content Fidelity, `context-pack/guardrails/AUDITOR_PROMPT.md`.

The orchestrator already references these by name and loads them once per run. It does **not** redefine or modify them — this engine never touches your rules.

## Before go-live
Run `python validate_pipeline.py` -> it must print `ALL CHECKS PASSED`. That confirms the Airtable `Status` options, the n8n workflow, and the orchestrator all use the same ASCII status strings and that every stage has a `Needs Attention` error route (the thing that stops the looping).
