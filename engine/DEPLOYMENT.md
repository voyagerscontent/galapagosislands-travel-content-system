# DEPLOYMENT — hard-coded wiring for one-trigger, loop-free content production

This is the single file any LLM (Perplexity, Claude Code, etc.) reads to run the
system. All connections are hard-coded in `config/SITE_CONFIG.md` (BRAND BLOCK →
`automation:`). To redeploy for another brand, edit that block only.

> **Secrets:** the `airtable_pat`, `n8n_api_key`, `airtable_base`, `airtable_table`,
> `n8n_base_url`, and `n8n_intake_webhook` values live in the SITE_CONFIG BRAND BLOCK.
> Fill them once; every consumer below reads them from there. (If this repo is public,
> use a private repo or repo secrets — baked tokens are visible to anyone with access.)

## Connections (read from SITE_CONFIG → automation)
| Purpose | SITE_CONFIG key | Used by |
|---|---|---|
| Airtable base | `airtable_base` (appXXXX) | trigger, n8n, orchestrator |
| Airtable table | `airtable_table` (tblXXXX = "Pages Master") | same |
| Airtable token | `airtable_pat` | trigger, n8n credential |
| n8n base URL | `n8n_base_url` | trigger |
| n8n intake webhook | `n8n_intake_webhook` | "produce next content" trigger |
| n8n API key | `n8n_api_key` | workflow management |

## The ONE trigger — "produce the next piece of content"
An LLM connected to this repo produces the next page by doing exactly this (no looping):

1. Read `config/SITE_CONFIG.md` → `automation:` values.
2. **Pick the next item:** query Airtable `airtable_base`/`airtable_table` for the
   record with the earliest `Status` in the chain that is NOT `Published`/`Needs Attention`
   (start at `Backlog`). If none exists, create one from `context-pack/briefs/SEED_BRIEFS.md`
   (Status = `Backlog`) — or POST the intake to `n8n_intake_webhook`.
3. **Advance exactly ONE stage** per the state machine in `01_PIPELINE_STATUS_MODEL.md`:
   read `Status` → do that stage's action (loading guardrails once) → write the next
   `Status`. Never re-evaluate "where am I" mid-run. One stage per turn.
4. **Loop safety (already enforced):** each stage has an input filter + a "not yet
   produced" guard + an error route to `Needs Attention` with `Return To`; `Attempt Count`
   caps retries at 2. A failure always leaves the queue. Terminal state = `Published`.
5. Stop after writing the new `Status`. The next invocation resumes deterministically.

Because the state field is a single ASCII `Status` with one producer / one consumer per
transition (see `00_WHY_IT_LOOPED_AND_FIXES.md`), a fresh LLM with no memory can drive it
without spinning: the record's `Status` IS the pointer.

## First-time setup (once per brand)
1. Fill the `automation:` block in `config/SITE_CONFIG.md`.
2. `python engine/build_airtable_base.py` → creates the "Pages Master" table with the
   canonical `Status` options + guard fields (`Attempt Count`, `Return To`, `Last Error`,
   `*_Link`). Uses `airtable_pat` + `airtable_base`.
3. Import `engine/n8n_pipeline_corrected.json` into n8n; it reads base/table/credential
   from `{{PLACEHOLDERS}}` resolved to the SITE_CONFIG values (see `hydrate_placeholders.py`).
4. `python engine/validate_pipeline.py` → must print `ALL CHECKS PASSED` (status strings
   aligned across Airtable + n8n + orchestrator — this is what prevents loops).
5. Perplexity: set Space custom instructions to `engine/02_ORCHESTRATOR_PERPLEXITY.md`
   and upload the load-order files (see `INSTALL_PERPLEXITY.md`). Claude Code: just point it
   at the repo and say "produce the next piece of content" — it follows this file.

## Guardrails always applied
Every run loads `context-pack/guardrails/*` and
`context-pack/what-to-write-about/source-of-truth/GALAPAGOS_FACTS_ADDENDUM.md` (incl. the
§0 HARD TRUTHS). Facts trace to the source-of-truth workbooks; brand comes from `{{BRAND}}`.
