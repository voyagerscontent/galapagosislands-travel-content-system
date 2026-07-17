# Pipeline Output Standard — v2
# GalapagosIslands.travel content production system
# Effective: July 2026

## Per-page deliverables (ALL three required from WF6 Polish onward)

Every page that passes Auditor Review produces three files:

| File | Format | Purpose |
|------|--------|---------|
| `CMS_Stage8_<Slug>.docx` | python-docx | Editorial review, Drive archive, human sign-off |
| `<slug>.html` | Self-contained HTML | Direct CMS paste or WordPress block import |
| `<slug>_schema.json` | JSON array | Paste into Yoast/RankMath structured data field |

## Spanish transposition (es-EC)

Every English page also produces a Spanish counterpart:

| File | Format | Notes |
|------|--------|-------|
| `CMS_Stage8_<Slug>_ES.docx` | python-docx | Same structure; Notas Webmaster block at top |
| `<slug>-es.html` | Self-contained HTML | `<html lang="es">`, hreflang pair, es-EC idiom |
| `<slug>-es_schema.json` | JSON array | Same schema, Spanish text values |

### What "transposition" means (not translation)
- Re-author for Spanish search intent and vocabulary (e.g. "isla Bartolomé", "Roca Pináculo")
- Ecuadorian/Latin American register — not Spain Spanish
- Adjust objections for the Spanish-speaking traveler profile (logistics from Ecuador, multigenerational travel, national park knowledge)
- Keep all facts, [source:] tags, and [VERIFY] flags identical to English version
- CTA in Spanish: "Habla con un Especialista en Galápagos"

### Webmaster Notes block (REQUIRED — top of every Spanish docx)
Every Spanish docx MUST open with a "Notas para el Webmaster" green box containing:
- Canonical URL: `/es/islands/<slug>/`
- hreflang pair: es + en + x-default
- Meta título (es): 50–60 chars
- Meta descripción (es): 140–160 chars
- Notas de transposición: what was reframed vs translated

## Full 8-stage chain (WF1–WF7 + human gate)

```
Scoring → Brief Ready → Drafting → Truth Check → Humanizing → Polishing → Auditor Review → Editor Review
```

### Stage outputs (what each stage writes)
| Stage | Output artifact | Airtable field |
|-------|----------------|----------------|
| WF1 Scoring | ROI sub-scores | ROI Score |
| WF2 Brief | Brief markdown | Brief Content |
| WF3 Draft | Draft markdown (with [source:] tags) | Draft Content |
| WF4 Truth Check | pass/fail + notes | (gate — no new artifact) |
| WF5 Humanize | Humanized markdown (natural cadence) | Humanized Content |
| WF6 Polish | .docx + .html + _schema.json + ES versions | Polished Content |
| WF7 Auditor | Parts A–G pass/fail report | Auditor Result |

### WF6 Polish outputs spec
- **docx**: python-docx ONLY. Append WF5–WF6 pipeline notes section. Teal H1/H2 RGB(1,105,111).
- **html**: self-contained (inline CSS). Design tokens from styles.css. JSON-LD in `<head>`. Standalone, no external dependencies.
- **schema.json**: JSON array of [BreadcrumbList, Article+speakable, FAQPage, Place/TouristDestination (for island pages)].

### Acceptance gate (WF6 must pass before Auditor)
- [ ] Meta title 50–60 chars, query-first
- [ ] Meta description 140–160 chars, answer-first
- [ ] One H1; clean H2/H3 tree; question-form headings
- [ ] Answer box ≤60 words, first screen, .answer-box class
- [ ] FAQ answers in FAQPage schema BYTE-MATCH visible page text
- [ ] speakable on .answer-box and .faq
- [ ] AIO blocks ≥4 (answer box, data table, key takeaways, FAQ)
- [ ] Every figure sourced or [VERIFY]
- [ ] One primary CTA, help-first, post-value
- [ ] No banned words
- [ ] Latin Trails: trade column only

## Slug categories (corrected July 2026)
Data authority pages sit inside their parent hub, not under /data/:

| Page | Slug |
|------|------|
| Visitor Site Ratings | `/islands/visitor-site-ratings/` |
| Island Comparison | `/islands/island-comparison/` |
| Cruise Fleet Index | `/cruises/fleet/` |
| Snorkel & Dive Site Rankings | `/snorkeling/site-rankings/` |
| Itinerary Duration Guide | `/cruises/itineraries/how-long/` |

## Internal citation standard
Pages that previously cited `visitor_sites.csv` or `ships.csv` must now cite the live data authority page:
- `[source: GalapagosIslands.travel Visitor Site Ratings — /islands/visitor-site-ratings/]`
- `[source: GalapagosIslands.travel Cruise Fleet Index — /cruises/fleet/]`

This builds internal PageRank to data authority pages and makes the site — not a private spreadsheet — the citable source for LLMs.
