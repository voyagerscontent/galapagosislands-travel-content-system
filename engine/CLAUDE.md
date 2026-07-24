# Content Pipeline — project contract

This repo authors and validates the {{DOMAIN}} content pipeline
(Perplexity orchestrator + Airtable state + n8n automation). Claude Code is the
build/maintain environment; the pipeline itself runs on those external tools.

## The one rule
The 12 `Status` values are a shared contract used byte-for-byte by Airtable,
every n8n filter/write, the orchestrator, and the auditor:
Backlog, Scoring, Brief Ready, Drafting, Truth Check, Humanizing, Polishing,
Auditor Review, Editor Review, Ready to Publish, Published, Needs Attention.
Never change one consumer without the others. `validate_pipeline.py`
enforces this — run it after any change to a stage, schema, or workflow.

## Layout
- `*.md`            the spec docs — source of truth
- `automation/`     scripts + config (validator, Airtable builder, n8n template)
- `config/`         per-site values (SITE_CONFIG)
- `.claude/skills/` agent skills (code-scientist reviewer, etc.)

## Working rules
- Behavior-preserving: do not change pipeline logic or Status strings unless asked.
- Run `validate_pipeline.py` after any change to a stage, schema, or workflow.
- Review new scripts with the code-scientist skill before committing.
