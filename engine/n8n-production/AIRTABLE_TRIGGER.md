# Run the pipeline from Airtable — set one cell, walk away

Change a record's **Status** to **Backlog** and the whole chain runs: Scoring → Brief Ready →
Drafting → Truth Check → Humanizing → Polishing → Auditor Review → **Editor Review**, writing the
editor Doc, the production `.html` and the `.schema.json` into *07 Polished for Editor* and emailing
the webmasters. No further clicks, no approvals, nothing to clear by hand.

This works because of two things already built:
- **Self-chaining** — each stage POSTs the next stage's webhook after it advances the record.
  One trigger runs the whole chain (WFP0–WFP6 chain forward; WFP7 stops at Editor Review, the
  human gate).
- **Idempotent intake** — WFP0 clears every downstream field when it claims a Backlog record
  (`make_intake_idempotent.py`). Re-running a finished page is just: set Status back to Backlog.

## Set up the Airtable automation (once, ~2 minutes)

Airtable's API cannot create automations, so this is a one-time UI step.

1. Open base **Content Production OS — GalapagosIslands.travel** (`appNkUL50eF601ejN`) →
   **Automations** → **Create automation**. Name it `Run production pipeline`.
2. **Trigger:** *When record matches conditions*
   - Table: **Pages Master**
   - Condition: **Status** `is` **Backlog**
3. **Action:** *Send HTTP request* (Airtable calls this "Send request")
   - Method: **POST**
   - URL: `https://voyagerscontent.app.n8n.cloud/webhook/galapagos-production/stage/intake`
   - Headers: `Content-Type` = `application/json`
   - Body (JSON):
     ```json
     {
       "site_id": "galapagosislands-travel-v1",
       "record_id": "{{ Airtable record ID }}"
     }
     ```
     Insert the record id via the blue **+** token picker → *Record ID*. Do not type it.
4. **Test** with any record, then toggle the automation **ON**.

That is the whole trigger. Everything downstream is already wired.

### Why "matches conditions" and not "when record updated"
*When record updated* fires on every edit and would re-trigger constantly. *Matches conditions*
fires once, on entry into the Backlog state — which is exactly "this page is ready to build".

## How to use it day to day

| You want | Do this |
|---|---|
| Build a new page | Fill `Name`, `Topic / Brief`, `Page Type`, `Pillar`, `Primary Keyword` → set **Status = Backlog** |
| Rebuild a finished page | Set **Status = Backlog**. Intake clears the old artifacts itself. |
| Rebuild after editing the brief | Same — edit `Topic / Brief`, set **Status = Backlog** |
| Resume a `Needs Attention` page | Set **Status** to the value in its **Return To** field, clear `Last Error`, and it resumes from that stage |
| Stop a page mid-run | Set Status to anything not in the chain. The next stage's claim guard finds nothing and halts. |

**Give the record a real brief.** `Topic / Brief` is what the Brief stage builds from — a one-line
stub produces a thin page. Say what to cover, what to ground, and any constraint that applies.

**`Page Type` decides the blueprint.** `Guide` and `Hub` are the built types (see `PAGE_TYPES.md`);
everything else currently routes to the guide blueprint. A guide page may never carry
Review/AggregateRating schema.

## What runs without you

| Stage | Does | Writes |
|---|---|---|
| WFP0 Intake | claims the record, **clears all downstream fields** | Status → Scoring |
| WFP1 Scoring | ROI / buyer intent / demand / ranking / conversion | scores → Brief Ready |
| WFP2 Brief | persona, funnel stage, CTA, outline, facts to ground | `Brief Content` + Doc in *03 Page briefs* |
| WFP3 Draft | full draft, `[source: …]` tagged, human enrichment placed verbatim | `Draft Content` + Doc in *04 First Drafts* |
| WFP4 Truth Check | every claim traced to the facts | pass → Humanizing, fail → Needs Attention |
| WFP5 Humanize | cadence only, facts untouched | `Humanized Content` + Doc in *06 Humanized* |
| WFP6 Polish | **publication boundary** — strips internal markers, assembles HTML, runs the conversion expert | `Polished Content`, `Conversion Review`, editor Doc + `.html` + `.schema.json` in *07 Polished for Editor*, emails the webmasters |
| WFP7 Auditor | full checklist; grounding judged against the draft, clean copy against the page | pass → **Editor Review** (stops; human gate) |

## When something stalls

A page sitting in one status with no error usually means a **claim guard miss** — the stage's
output field was already populated, so it refused to re-claim. Intake prevents this for a full
re-run; it can still happen if you POST a mid-chain webhook by hand. Fix: set Status to Backlog
and let intake reset it.

Executions are visible at `https://voyagerscontent.app.n8n.cloud` → Executions, filtered by
workflow. IDs are in `README.md`.

## Deterministic gates (not the LLM's judgement)

Some checks are measured in code, in `Validate Output`, because a language model cannot be
trusted to do them — the auditor once passed a 163-character meta description as "158 chars":

- `<title>` must exist as a real element and be 50–60 characters
- `<meta name="description">` must exist and be 140–160 characters
- stray markdown (`**bold**`) is converted to real tags; `~$200` is rewritten to `about $200`

A page failing a meta gate routes to Needs Attention with the measured length in `Last Error`,
rather than shipping a bad tag to the CMS.
