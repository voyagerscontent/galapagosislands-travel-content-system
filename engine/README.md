# {{DOMAIN}} — Corrected Pipeline (drop-in)

This folder fixes the pipeline that made Perplexity run in circles. It changes **only the state machine and wiring** — the rule/guardrail documents in `00 Master Rules` are untouched and are referenced as-is.

Read `00_WHY_IT_LOOPED_AND_FIXES.md` first.

## Contents
```
00_WHY_IT_LOOPED_AND_FIXES.md   diagnosis + every fix
01_PIPELINE_STATUS_MODEL.md     the single 12-state machine (the contract)
02_ORCHESTRATOR_PERPLEXITY.md   deterministic Space prompt (loop-safe)
config/SITE_CONFIG.md           per-site values + fork template
automation/airtable_schema.json clean Status single-select + guard fields
automation/build_airtable_base.py
automation/n8n_pipeline_corrected.json  corrected stage template (guard + error route)
validate_pipeline.py            consistency + anti-loop checker (run before deploy)
```

## Deploy a clean instance

1. **Validate:** `python validate_pipeline.py` -> must print `ALL CHECKS PASSED`.
2. **Perplexity Space:** set the Space custom instructions to `02_ORCHESTRATOR_PERPLEXITY.md`. Upload `01_PIPELINE_STATUS_MODEL.md` and `config/SITE_CONFIG.md` alongside the existing 12 rule files (do not replace the rule files).
3. **Airtable:** either run `python automation/build_airtable_base.py --pat <PAT> --base-id <BASE>` on a new base, or just confirm the existing base `appNkUL50eF601ejN` has the `Status` options exactly as in `airtable_schema.json` and add the guard fields (`Attempt Count`, `Return To`, `Last Error`, and the `*_Link` fields).
4. **n8n:** import `automation/n8n_pipeline_corrected.json`; it is the Brief stage as a corrected template. Clone the node group for each of the 5 stages, changing only the input `Status`, output `Status`, guard field, and LLM action. Keep the `Needs Attention` branch on every stage. Replace `{{AIRTABLE_BASE_ID}}`, `{{AIRTABLE_TABLE_ID}}`, `{{SITE_NAME}}`.

## The one rule that prevents loops
The status values are a **shared contract**. Airtable options, every n8n filter/write, the orchestrator, and the auditor must use the same ASCII strings. `validate_pipeline.py` enforces this; run it whenever you touch a stage.
