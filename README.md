# {{DOMAIN}} — Content Production System

A self-contained, **duplicable** content-production project for the entire `{{DOMAIN}}` ecosystem. It ships into a Perplexity Space and runs on the existing loop-free engine + Airtable + n8n. Clone the folder and swap the context pack to serve another site.

## Architecture (two layers)
```
engine/          the website-AGNOSTIC pipeline (12-state machine, orchestrator,
                 Airtable schema, n8n template, validator) — COPIED UNCHANGED.
context-pack/    the per-site brain for {{DOMAIN}}:
  who-to-write-for/      persona + conversion architecture
  brand-voice/           brand style guide (voice, banned words, clichés)
  what-to-write-about/
    source-of-truth/     island facts, ships, trip-types, 106 content rules (REBRANDED)
    ship-data/           ECO/VALUE/WOW/ITINERARY ratings + advisor specs/itineraries
    page-templates/      ranking hub-page template + spec + ACF map
  guardrails/            Guardian of Truth, Content Fidelity, Entity Rules, Auditor
  briefs/                seed page briefs
interface/       team intake: Airtable form/interface + hosted intake-form.html
                 (adding data = activating the pipeline; optional human enrichment)
produced-content/ worked sample pages produced by the system (hub + FAQ)
  AGENT_MANDATORY_BRIEFING.md   who we are + the production sub-steps
  MASTER_FACTS_FILE.md          grounding facts + data pointers
  CONTENT_GENERATION_PROMPT.md  sequences the 5 components into one procedure
config/SITE_CONFIG.md   the only per-site values
INSTALL_PERPLEXITY.md   how to ship it into a Space
```

## How the five components became pipeline steps
The engine's 12 `Status` states are **unchanged** (they are a shared contract across all sites). The components run as **named sub-steps inside existing stages** (see `AGENT_MANDATORY_BRIEFING.md`):

| Component | Sub-step | Engine stage |
|---|---|---|
| Audience persona builder | A · Audience & Conversion mapping | Brief Ready |
| Hub-page template | B · Page-type blueprint | Brief Ready |
| Source-of-truth + ship data | C · Facts grounding | Brief → Drafting |
| Brand style guide | D · Brand-voice drafting | Drafting |
| (truth) | E · Truth Check | Truth Check |
| Brand + persona | F · Brand-voice & persona gate | Auditor Review |

## One-time rebrand applied (this run)
The source-of-truth (rebuilt from a galapagosislands.com scrape) was rewritten for this site:
`galapagosislands.com → {{DOMAIN}}` (1,700×) and `{{BRAND}} → "{{BRAND}}" / "{{BRAND}}"` (varied; 1,105×). The original builders/data in `claude-tutorial` are **untouched** and still serve other sites.

## Run it
1. `python engine/validate_pipeline.py` → `ALL CHECKS PASSED` (engine unchanged).
2. Follow `INSTALL_PERPLEXITY.md` to upload engine + context pack to a Space.
3. Create the Airtable base, import the n8n workflow, point at this site's credential.
4. Set up the team intake (`interface/AIRTABLE_INTAKE_FORM.md`): add the intake fields and either an Airtable Form view or host `interface/intake-form.html`. Adding a record (Status = Backlog) activates the sequence.

## Launch a page (anyone on the team)
Submit the intake form (Airtable form or the hosted page). Required: title, page type, topic, persona, funnel stage. **Optional human enrichment** — paragraphs, quotes, anecdotes, contributor — is woven in verbatim and attributed (the engine never paraphrases human text). No enrichment = the page is produced normally.

## Clone for another site
Copy this folder, replace `config/SITE_CONFIG.md`, swap the `context-pack/` (new personas, brand voice, facts, briefs). Keep `engine/` and the 12 `Status` values identical.
