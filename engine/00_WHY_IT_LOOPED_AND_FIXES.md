# Why the pipeline ran in circles — diagnosis and fixes

**Site:** oceanalbatros.com · **Scope:** pipeline mechanics only. The guardrail/rule documents (Guardian of Truth, Content Fidelity, Agent Mandatory Briefing, Master Facts, humanization prompts, personas, auditor checklist) are **not modified**. Only the *state machine, orchestration, Airtable schema, and n8n wiring* are corrected.

I reviewed the System Replication Manual, the Pipeline Replication Starter, the Auditor Agent prompt, and the actual deployed n8n workflows (`content_factory_n8n_workflows.zip`) and Airtable base `appNkUL50eF601ejN`. Five concrete defects caused the looping/stalling. None of them are in the rules; all are in the plumbing.

## Root causes

### 1. Two conflicting state vocabularies (the main cause)
The deployed n8n workflows key off a simple ASCII **`Status`** field with values like `Scoring`, `Brief Ready`, `Drafting`. But the manuals, the Auditor prompt, and the Replication Starter simultaneously describe a **`Content Stage`** field with *49 single-select options* and *25 fractional gates* (`0.1`–`0.7`, `2a`, `2a.5`, `5a/5b/5c`, `7a–7c`, `10`, `13`), several using em-dashes.

An orchestrator (Perplexity) told to "advance the page through the pipeline" cannot tell which field is authoritative or which of two non-matching stage names a record is really at. So it re-reads the rules, re-evaluates the stage, and never converges — it loops. **Fix:** one canonical state field. The System Replication Manual already specifies a clean 11-state chain in Part 3.2 — we standardize *everything* on that and retire the 49-option/25-gate scheme from the operational layer.

### 2. No error or lock state in the polling workflows
Each n8n workflow polls every 5 minutes for records in its input status. Workflow 1 (ROI Scoring) filters `{Status} = 'Scoring'`, calls GPT-4o, parses JSON, then writes the next status. **There is no guard and no error route.** If GPT returns text that won't parse, the final "update status" node never runs, the record stays in `Scoring`, and the workflow re-scores the *same record every 5 minutes forever* — burning tokens and going in circles. (Workflow 2 partially avoids this by also checking `{Brief Link} = ''`, which is the pattern all stages need.)
**Fix:** every stage gets (a) a precise input filter **plus a "not yet produced" guard**, and (b) an explicit failure route to a `Needs Attention` status with a `Return To` field. A failure must always leave the input queue.

### 3. Auditor re-loop with no iteration cap
The Auditor rule is "any single FAIL = overall FAIL → return to the earliest failing stage, re-audit after correction." That is correct as a *rule*. But operationally nothing caps the number of round trips, so a page that keeps missing one threshold ping-pongs Truth Check → Draft → Humanize → Audit → Truth Check indefinitely.
**Fix (pipeline only, rule untouched):** the orchestrator enforces a **retry counter** (`Attempt Count`, max 2). On the 3rd failure of the same stage it routes to `Needs Attention` for a human, instead of looping. The auditor's pass/fail criteria are unchanged.

### 4. Non-deterministic orchestration
"Every agent must load all guardrail files at the START of every session" is essential for accuracy, but with no notion of *session state* the orchestrator re-loads and re-initializes on every step, re-deriving "where am I" each time. Combined with #1 it produces visible spinning.
**Fix:** the corrected orchestrator loads guardrails **once per run**, then loops a single deterministic step: read `Status` → do exactly that stage's action → write the next `Status` (or `Needs Attention`) → stop. One stage per turn. Explicit terminal state `Published`.

### 5. Hand-off strings not guaranteed to match
Polling workflows only advance a record if the downstream filter equals the upstream output **byte-for-byte**. `Brief Ready` (WF1 out) matches `Brief Ready` (WF2 in) — good — but the manual's parallel names (`Stage 2 — ROI Scoring`, em-dash) match nothing the workflows look for, so any agent driving by the manual's names stalls.
**Fix:** a single ordered status list defined once (`PIPELINE_STATUS_MODEL.md`) and rendered identically into Airtable, the workflow, the orchestrator, and the auditor hand-off notes. `validate_pipeline.py` fails the build if any consumer/producer string drifts.

## The corrected operational state machine (one field: `Status`)

```
Backlog → Scoring → Brief Ready → Drafting → Truth Check → Humanizing
        → Polishing → Auditor Review → Editor Review → Ready to Publish → Published
                                   ⮑ (any failure) → Needs Attention → (Return To)
```

This is exactly the chain the System Replication Manual Part 3.2 already documents. Every value is plain ASCII (no em-dashes), every transition has one producer and one consumer, every stage has an error route, and there is one terminal state. See `01_PIPELINE_STATUS_MODEL.md`.

## What changed, file by file

| File | Change |
|---|---|
| `01_PIPELINE_STATUS_MODEL.md` | New single source of truth for the 11 states + `Needs Attention`; each state's actor, input guard, output, error route. |
| `02_ORCHESTRATOR_PERPLEXITY.md` | Deterministic Space prompt: load guardrails once, one stage per turn, retry cap, terminal state. References existing rule files by name; does not change them. |
| `automation/airtable_schema.json` | `Status` single-select with the 12 canonical options; adds guard fields (`Brief Link`, `Draft Link`, `Humanized Link`, `Polished Link`), `Attempt Count`, `Return To`, `Last Error`. |
| `automation/n8n_pipeline_corrected.json` | One importable workflow per stage pattern with precise filter **+ production guard + error route**; base/table/credential via `{{PLACEHOLDERS}}`. |
| `automation/build_airtable_base.py` | Builds the schema; skips computed fields. |
| `config/SITE_CONFIG.md` | oceanalbatros values + blank fork template (keeps it website-agnostic). |
| `validate_pipeline.py` | Verifies status-string consistency across schema + workflow + orchestrator, one-producer/one-consumer, error route per stage, terminal state present. |

**Rules left untouched:** every file in `00 Master Rules` (guardrails, facts, prompts, personas, auditor checklist) is referenced as-is. The fixes are entirely in the state machine and wiring.
