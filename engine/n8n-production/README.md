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

## Built
| Workflow | n8n id | Active | Purpose |
|---|---|---|---|
| WFP0 Production Intake | `i8xtkx9GBw1aRdkP` | **inactive** | webhook → registry lookup → claim-guard (Status=Backlog + record match) → advance Backlog→Scoring, else Needs Attention |

WFP0 mirrors the proven WF0 pattern minus the optimization "page must already
exist" gate. Created **inactive** for review; activate after testing.
Intake URL (once active): `https://voyagerscontent.app.n8n.cloud/webhook/galapagos-production/stage/intake`
Payload: `{ "site_id": "galapagosislands-travel-v1", "record_id": "recXXneed", ... }`

## Remaining (each = the WF3 pattern: filter+guard → Anthropic → validate → advance | Needs Attention)
- WFP1 Scoring, WFP2 Brief Ready, WFP3 Drafting, WFP4 Truth Check, WFP5 Humanizing,
  WFP6 Polishing, WFP7 Auditor Review → then human Editor Review → Ready to Publish → Published.
- **Blocker for output stages:** where drafts land. Either (a) add a Google Drive
  OAuth credential in n8n (write Google Docs), or (b) store drafts in an Airtable
  long-text field (no Drive dependency). Decide before building WFP3 Drafting.
- **Trigger:** Airtable automation on the Galápagos base → "When Status is one of
  [the working stages] → POST to the stage webhook" with `{site_id, record_id}`.
  (Airtable automations are created in the Airtable UI, not the API.)

## Loop-safety (unchanged contract)
One `Status` field; each stage has input filter + output guard + error route to
`Needs Attention` + `Attempt Count` cap. Run `engine/validate_pipeline.py` after
changes. Never edit the 12 status strings per site.
