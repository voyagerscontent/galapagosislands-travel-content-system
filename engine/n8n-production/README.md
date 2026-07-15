# Production pipeline — n8n build (content PRODUCTION, new pages)

Separate from the live **Weboptimizer** optimization pipeline (WF0–WF8). This set
produces NEW pages on the production status model:
`Backlog → Scoring → Brief Ready → Drafting → Truth Check → Humanizing → Polishing → Auditor Review → Editor Review → Ready to Publish → Published` (+ `Needs Attention`).

## Instance
- n8n: `https://voyagerscontent.app.n8n.cloud`
- Credentials present: Anthropic (`fQbptY6CtcIWVwYp`), Airtable (`mITfEGdTPqCCNrsT`), SMTP, DataForSEO.
- **Missing: a Google Drive credential** — required for stages that write Docs to Drive.

## Multi-tenant registry (built)
- Ops base `appPlU9eC5GL6ncjZ` → table **Content Production Sites** `tblOkOXzm2GZUMkYs`.
- Row: `galapagosislands-travel-v1` → Base `appNkUL50eF601ejN`, Table `tblUgxSGGfeJIL5GD`,
  Drive folder `1_Tliljbgdl0HBqBcBfrtd6CPHMdOmtaE`, intake path `galapagos-production/stage/intake`.

## Built — ALL stages (inactive, for review before activation)
| Workflow | n8n id | Webhook path | Transition |
|---|---|---|---|
| WFP0 Production Intake | `i8xtkx9GBw1aRdkP` | `…/intake` | Backlog → Scoring |
| WFP1 Scoring | `zJKqFEmA9FYDJYXh` | `…/scoring` | Scoring → Brief Ready |
| WFP2 Brief Ready | `cFY7Tz5q2ih2UCvt` | `…/brief` | Brief Ready → Drafting |
| WFP3 Drafting | `eExgOTVFIoCuJb0D` | `…/draft` | Drafting → Truth Check |
| WFP4 Truth Check | `ZsrCHmeSCy8P4Wb2` | `…/truthcheck` | Truth Check → Humanizing \| Needs Attention |
| WFP5 Humanizing | `yh9kMFkbPY34vmVJ` | `…/humanize` | Humanizing → Polishing |
| WFP6 Polishing | `U0MrpTN3hv4RfNMI` | `…/polish` | Polishing → Auditor Review |
| WFP7 Auditor Review | `na9GWyR851UHSlbP` | `…/auditor` | Auditor Review → Editor Review \| Needs Attention |

Base webhook: `https://voyagerscontent.app.n8n.cloud/webhook/galapagos-production/stage/<path>`
Payload: `{ "site_id": "galapagosislands-travel-v1", "record_id": "recXXXX" }`
Each stage stores its artifact in an Airtable long-text field (`Brief/Draft/Humanized/Polished Content`)
with `<X> Link = airtable://<X> Content`, matching the proven Weboptimizer pattern.
Editor Review → Ready to Publish → Published are human/publish steps (not LLM stages).

## Verified (2026-07-15 controlled test on a throwaway record)
WFP1 fired end-to-end: **Webhook ✓ → Registry lookup ✓ → Claim-guard ✓** → Anthropic ✗.
The ONLY failure was `Your credit balance is too low to access the Anthropic API` on the
`Anthropic - Weboptimizer` credential. Plumbing is correct; **top up Anthropic credits** to run.

## Self-chaining (built) — no Airtable automation needed
WFP0–WFP6 each end with a **"Trigger next stage"** HTTP node that POSTs
`{site_id, record_id}` to the next stage's webhook right after the Advance step.
So one POST to the intake webhook (or setting a record to Backlog + POSTing intake)
runs the whole chain autonomously to **Editor Review**, where WFP7 stops (human gate).
Applier: `add_self_chaining.py`. On the `Needs Attention` branch nothing chains (it halts).

## Remaining to go live
1. **Top up Anthropic API credits** (account behind the `fQbptY6CtcIWVwYp` credential) — the one true blocker (verified by the controlled test).
2. **Activate** WFP0–WFP7 (currently inactive). Activate each; activation registers its webhook.
3. **Kick off** a record: POST `{site_id:'galapagosislands-travel-v1', record_id:'recXXXX'}` to
   `…/webhook/galapagos-production/stage/intake` (record must be at `Backlog`). It self-chains to Editor Review.
4. **Google-Doc export (enhancement):** add a Google Drive credential in n8n, then a Drive node on
   the output stages writes a real Doc into folder `1_Tliljbgdl0HBqBcBfrtd6CPHMdOmtaE` alongside the `airtable://` link.

## Loop-safety (unchanged contract)
One `Status` field; each stage has input filter + output guard + error route to
`Needs Attention` + `Attempt Count` cap. Run `engine/validate_pipeline.py` after
changes. Never edit the 12 status strings per site.
