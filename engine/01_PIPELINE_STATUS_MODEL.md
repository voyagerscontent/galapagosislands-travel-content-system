# Pipeline Status Model (single source of truth)

One field governs the whole pipeline: **`Status`** (Airtable single-select). Plain ASCII, no em-dashes. Every record sits in exactly one state. Every transition is produced by exactly one actor and consumed by exactly one next actor. Every working state has an error route to `Needs Attention`.

This replaces, for OPERATIONS, the older `Content Stage` (49-option) and the 25 fractional gates. Those remain valid as descriptive rule documentation but are no longer the runtime state. The agent roles, guardrails, and auditor checklist are unchanged — they just read/write this one field.

## The 12 states

| # | `Status` value | Actor (agent / workflow) | Enters when | Input guard (must also be true) | On success set | On failure set |
|---|---|---|---|---|---|---|
| 0 | `Backlog` | Human / Planner | page created | — | `Scoring` | — |
| 1 | `Scoring` | ROI workflow (n8n WF1) | moved from Backlog | `ROI Score` is empty | `Brief Ready` | `Needs Attention` |
| 2 | `Brief Ready` | Brief workflow (WF2) | WF1 done | `Brief Link` is empty | `Drafting` | `Needs Attention` |
| 3 | `Drafting` | Draft workflow (WF3) | WF2 done | `Draft Link` is empty | `Truth Check` | `Needs Attention` |
| 4 | `Truth Check` | Guardian agent (WF4a) | WF3 done | `Draft Link` not empty | `Humanizing` | `Needs Attention` |
| 5 | `Humanizing` | Humanizer (WF4b) | Truth passed | `Humanized Link` is empty | `Polishing` | `Needs Attention` |
| 6 | `Polishing` | Polish workflow (WF5) | WF4 done | `Polished Link` is empty | `Auditor Review` | `Needs Attention` |
| 7 | `Auditor Review` | Auditor agent | WF5 done | `Polished Link` not empty | `Editor Review` | `Needs Attention` |
| 8 | `Editor Review` | Human editor | auditor PASS | — | `Ready to Publish` | `Needs Attention` |
| 9 | `Ready to Publish` | Human editor | editor approves | — | `Published` | — |
| 10 | `Published` | — (terminal) | published live | `Published URL` not empty | — | — |
| E | `Needs Attention` | Human | any failure | — | (see `Return To`) | — |

## Guard rules that prevent re-processing loops

1. **Production guard.** A workflow only picks up a record if its expected output does not already exist. Example filter for the Brief stage:
   `AND({Status} = 'Brief Ready', {Brief Link} = '')`. After it writes `Brief Link` and advances to `Drafting`, it can never re-select that record even if it briefly remains visible to the poll.
2. **Single consumer.** Exactly one workflow filters on each working status. No two workflows share an input status, and no filter uses `contains`/`!=` (which can match multiple states). Always `=`.
3. **Error route, always.** If the LLM call, JSON parse, or Drive write fails, the workflow sets `Status = 'Needs Attention'`, writes `Last Error`, and copies the current stage into `Return To`. The record leaves the working queue, so it is never re-polled in a tight loop.
4. **Retry cap (orchestrator).** The orchestrator increments `Attempt Count` each time it enters a working stage for a given record. On the 3rd consecutive failure of the same stage it forces `Needs Attention` instead of bouncing the record backward again. This caps the auditor "return to earliest failing stage" loop without changing the auditor's pass/fail rules.
5. **Resume from `Needs Attention`.** A human fixes the issue and sets `Status` back to the value in `Return To` (and clears `Last Error`, resets `Attempt Count`). Flow continues.

## Hand-off contract (must match byte-for-byte)

```
Backlog --(Planner)--> Scoring
Scoring --(WF1)--> Brief Ready
Brief Ready --(WF2)--> Drafting
Drafting --(WF3)--> Truth Check
Truth Check --(WF4a Guardian)--> Humanizing
Humanizing --(WF4b Humanizer)--> Polishing
Polishing --(WF5)--> Auditor Review
Auditor Review --(Auditor)--> Editor Review
Editor Review --(human)--> Ready to Publish
Ready to Publish --(human)--> Published   [TERMINAL]
ANY working stage --(failure)--> Needs Attention --(human)--> {Return To}
```

`validate_pipeline.py` asserts: every value used by the workflow and orchestrator exists in this list; every working state has one producer and one consumer; every working state has an error route; exactly one terminal state. Build fails otherwise.

## Mapping to the rule documents (unchanged)

The agents and checks still run exactly as written in `00 Master Rules`:
- `Scoring` runs the ROI scoring rubric (Buyer Intent, Search Demand, Ranking Chance, Conversion Value).
- `Truth Check` runs Guardian of Truth + MASTER_FACTS_FILE + Content Fidelity.
- `Humanizing` runs the humanization prompts (detector-neutral; no camouflage).
- `Auditor Review` runs `auditor_agent_prompt.md` Parts A–G.
- Entity rules (Latin Trails = GSA, Polar Latitudes = operator, Chimu unmentioned, Marcel Perkins title) apply throughout.
Only the *state field they read and write* is unified here.
