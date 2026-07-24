# DEPRECATED — add_bcp_injector.py (WFP5 version)

**Status:** Superseded as of July 24, 2026. Do not run.

## Why it was deprecated

`add_bcp_injector.py` originally wired a 258KB compiled-lexicon JS blob into
WFP5 (Humanize) as the "BCP Inject" code node at the absolute end of that stage.

**Problem:** WFP6 (Polishing) runs after WFP5 and REWRITES the prose in full,
wiping every injected word and salt sentence. Running injection in WFP5 was
therefore a no-op — the injected content never reached the published page.

## What replaced it

1. **`add_bcp_injector_wf7.py`** — moved the inline JS BCP node to WFP7 (Auditor),
   which runs AFTER WFP6 polishing and is the last stage before Editor Review.
   This is the current live implementation (WFP7: `BCP Inject (HTML)` node).

2. **`wire_pipeline_service.py`** — replaces the inline 258KB JS blob in WFP7 with
   a clean HTTP call to the Python `content-pipeline` FastAPI service, which runs
   full POS-confirmed injection (adjectives AND verbs, nltk-tagged) and per-paragraph
   salt (1 injection per eligible paragraph, alternating long/phrase by index).

## Current pipeline order (correct)

```
WFP5 Humanize  → WFP6 Polish  → WFP7 Auditor
                                  └── QA Gate (code)
                                  └── LLM Auditor
                                  └── Pipeline Inject (HTTP) ← Python service
                                  └── Inject Check (code)
                                  └── Advance to Editor Review
```

The file `add_bcp_injector.py` is kept in the repo for historical reference only.
