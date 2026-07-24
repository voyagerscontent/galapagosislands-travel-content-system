# MARKETMUSE PROCESS — {{DOMAIN}}

**Hub and Pillar pages only.** A human gate between Brief Ready and Drafting: the pipeline writes
the brief, then stops and waits for a MarketMuse pass before anything is drafted. Guides, FAQs,
wildlife, island and blog pages never stop here — they chain straight through.

Commercial category pages are where topical coverage decides whether the page ranks at all, so
they get a human topic-model pass. An informational guide does not need one, and gating it would
just add a manual step for no gain.

## The flow

```
WFP1 Scoring ──► WFP2 Brief writes the brief
                     │
                     ├─ Page Type is Hub or Pillar AND MarketMuse Score is empty
                     │     └─► HOLD at Status = Brief Ready  ◄── the gate. Nothing chains.
                     │              │
                     │              │  ── HUMAN: run MarketMuse, fill two fields ──
                     │              ▼
                     │         Automation fires ──► Status = Drafting ──► WFP3
                     │
                     └─ anything else ──► Status = Drafting ──► WFP3 (no stop)
```

The record sits at **Brief Ready** with its brief written and its Doc in *03 Page briefs*. It does
not re-fire while it waits: WFP2's claim guard requires `{Brief Content} = ''`, and the brief is
now filled.

## What the human does

1. The record is at **Brief Ready**, Page Type Hub or Pillar. Open its brief Doc (`Brief Link`).
2. Run the page's target topic in **MarketMuse**.
3. Fill **two fields** on the record:

| Field | What goes in it |
|---|---|
| **MarketMuse Score** | the content score MarketMuse returns (a number). **This field is the gate** — filling it releases the page. |
| **Target Keywords (NW/MM)** | the suggested term list, comma-separated. WFP3 drafts to cover these. |

4. That is all. The automation moves the record to **Drafting** and the chain resumes on its own,
   through to Editor Review.

**Fill Target Keywords before (or with) the Score.** The Score is the trigger — set it last, or the
page may start drafting without the terms.

## What the pipeline does with it

`WFP3 Drafting` receives both fields and is told to work the target terms in naturally where they
fit the brief's outline. The terms are a **coverage checklist, not a quota**: never stuff a term,
never bend a sentence around one, and never let a term override the FACTS, the HARD TRUTHS or the
brand voice. A term that has no honest place on the page is left out.

The Score is not published and never appears in copy. It is a gate and a record, nothing more.

## Releasing a page manually

If a page should proceed without MarketMuse, set **MarketMuse Score** to `0` and leave Target
Keywords empty. The gate opens (the field is no longer empty) and the draft runs without terms.
Recorded as an explicit decision rather than a silent skip.

## Re-running a gated page

Setting **Status = Backlog** re-runs from scratch — and WFP0's intake reset **clears
MarketMuse Score**, so the page will stop at the gate again and want a fresh pass. That is
deliberate: a rebuilt brief deserves a re-check. To re-draft *without* redoing MarketMuse, set
**Status = Drafting** and clear `Draft Content` instead of going back to Backlog.

## Airtable automation (one-time setup)

See `engine/n8n-production/AIRTABLE_TRIGGER.md` — automation **#2 "Release MarketMuse gate"**.
