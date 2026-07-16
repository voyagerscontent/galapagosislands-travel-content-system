# Production pipeline — n8n build (content PRODUCTION, new pages)

Separate from the live **Weboptimizer** optimization pipeline (WF0–WF8). This set
produces NEW pages on the production status model:
`Backlog → Scoring → Brief Ready → Drafting → Truth Check → Humanizing → Polishing → Auditor Review → Editor Review → Ready to Publish → Published` (+ `Needs Attention`).

## Instance
- n8n: `https://voyagerscontent.app.n8n.cloud`
- Credentials present: Anthropic (`fQbptY6CtcIWVwYp`), Airtable (`mITfEGdTPqCCNrsT`),
  **Google Drive (`BXOLO4YcNnpHp3SD`)**, SMTP, DataForSEO.

## Multi-tenant registry (built)
- Ops base `appPlU9eC5GL6ncjZ` → table **Content Production Sites** `tblOkOXzm2GZUMkYs`.
- Row: `galapagosislands-travel-v1` → Base `appNkUL50eF601ejN`, Table `tblUgxSGGfeJIL5GD`,
  Drive folder `1_Tliljbgdl0HBqBcBfrtd6CPHMdOmtaE`, intake path `galapagos-production/stage/intake`.

## Built — ALL stages (ACTIVE; verified end-to-end 2026-07-16)
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

## LIVE — verified end-to-end (2026-07-16)
`rec00MZWBXL4n8yRm` "Daily Budget on the Galápagos" ran Backlog → **Editor Review** with a clean
auditor pass: 0 marker leaks, 0 guardrail echo, `<title>` 55 chars, 4 Docs written to Drive.

**Kick off a record:** POST `{site_id:'galapagosislands-travel-v1', record_id:'recXXXX'}` to
`…/webhook/galapagos-production/stage/intake` (record must be at `Backlog`, and every
`* Content` field must be empty — the stage claim-guards check `{X Content} = ''`).
It self-chains to Editor Review. To resume a `Needs Attention` record, set `Status` to the
`Return To` value, clear `Last Error`/`Return To`, and POST that stage's webhook directly.

## Google Doc export (built — `add_drive_export.py`)
Content stages write a real Google Doc into the ContentEngine stage folder and set the record's
`* Link` to the Doc URL. QA stages (WFP4/WFP7) emit pass/fail + notes, not documents, so they
export nothing — their findings live in `Truth Check Notes` / `Audit Notes`.

| Stage | Drive folder | Folder id |
|---|---|---|
| WFP2 brief | `03 Page briefs` | `1SF2xCX0_ZLVLtdMV0HCADeeRqnhPuTTh` |
| WFP3 draft | `04 First Drafts` | `1DRmnqM32E40vKB_9JRJNO-yPLD1hl2Nb` |
| WFP5 humanize | `06 Humanized` | `1IFBQB6v6ht2jS4mNm5RPjMZryf4ro-9Y` |
| WFP6 polish | `07 Polished for Editor` | `1jf8kwaFmFHpYTgmLYSVSMU4yq-YBM5bH` |

Inserted as `Output OK? --true--> Export to Drive --> Advance to X`. Because the Drive node
replaces `$json`, each `Advance to X` reads the record/artifact from `$('Validate Output')`
explicitly. Drive failure is non-fatal (`continueRegularOutput`) — Airtable stays the system of
record and the Link falls back to `airtable://<field>`.

**Known rough edge:** WFP6's artifact is production HTML, so its Doc in `07 Polished for Editor`
contains HTML source rather than readable prose. Fine for CMS hand-off, awkward for a human
editor. Options: export `.html` un-converted, or render a reader-facing Doc alongside it.

## The guardrail-leak class of bug (fixed 2026-07-16 — read before touching prompts)
Pages were shipping internal grounding markers (`[GC][GCT][CDF]`) in body copy, tables and
JSON-LD — 100+ on the land-iguana page — and reciting their own guardrails as prose
("with no operator favoritism", "Luxury is the boat, not the map"). Three causes, all fixed:
1. `enrich_stage_prompts.py` told every stage to "cite its tag". Markers are now declared
   **internal**, required at draft, forbidden at publication (`GROUNDING` block).
2. WFP6's task said "keep every grounded fact **and citation** intact" — which kept the tags.
   Polish is now explicitly the publication boundary and must strip them.
3. `GUIDE_PAGE_SPEC.md` demanded HARD TRUTHS "always both, where relevant", so a wildlife page
   got a stock timing paragraph. HT-1/HT-2 are now constraints on claims, copy only on-topic.

**Every stage prompt states its own position in the chain.** This matters: the first fixed run
failed because WFP4 applied the *publication* standard to a *draft* and rejected the very markers
the draft is required to carry. A stage that doesn't know where it sits will judge by the wrong
standard. `WFP5` was also running the old 1.6k-char prompt with no context pack — it now shares
the same head as the rest.

## Loop-safety (unchanged contract)
One `Status` field; each stage has input filter + output guard + error route to
`Needs Attention` + `Attempt Count` cap. Run `engine/validate_pipeline.py` after
changes. Never edit the 12 status strings per site.
