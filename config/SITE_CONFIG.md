# SITE_CONFIG — content production system

This is the **only** file you edit to redeploy the system for a different brand.
Change the BRAND BLOCK below and every guardrail, fact file, and prompt adjusts,
because they reference the tokens `{{BRAND}}`, `{{DOMAIN}}`, `{{BRAND_ALT}}`,
`{{PRIMARY_CTA}}` and `{{CONTRIBUTORS}}` instead of hard-coded names.

The engine (status model, orchestrator, schema, workflow) stays identical and is
NOT edited here. `status_values` are byte-for-byte identical across every site.

---

## BRAND BLOCK  (edit these to re-brand the whole system)

```yaml
# --- identity -------------------------------------------------------------
BRAND: "Galapagos Islands.Travel"          # display name used in copy
BRAND_ALT: "galapagosislands.travel"       # spoken/alt form; also the domain label
DOMAIN: "galapagosislands.travel"          # canonical domain (links, emails, citations)
TAGLINE: "an independent editorial travel guide to the Galápagos"

# --- publisher / relationship --------------------------------------------
# The guide is run by two operators, disclosed in the footer CTA (see below):
# Voyagers Travel Company (consumer travel planning) and Latin Trails (Galápagos DMC / trade).
PUBLISHER: "Voyagers Travel Company & Latin Trails"
PUBLISHER_NOTE: "This guide is run by Voyagers Travel Company (traveller planning) and Latin Trails (Galápagos DMC services for the trade)."

# --- conversion -----------------------------------------------------------
# The CTA is a SUBTLE dual close hardcoded at the foot of every page — see
# context-pack/guardrails/CTA_BLOCK.md for the verbatim copy and rules.
PRIMARY_CTA: "Travelers can contact Voyagers Travel Company for a full travel-planning service. Travel agents and tour operators looking for expert DMC services in the Galápagos can reach out to Latin Trails."
CTA_TRAVELER_URL: "https://www.voyagerstravel.com"   # ⚠ webmaster: confirm the exact Voyagers URL
CTA_TRADE_URL: "https://www.latintrails.com"

# --- contributors (optional) ---------------------------------------------
# Named expert voices to attribute where authorship is shown. Leave empty to
# run brand-voice only (no named contributors). Reusable: swap per brand.
CONTRIBUTORS: ["Juan Magallanes (Galápagos Travel Advisor)", "Andre Robles (Voyagers Travel Company)", "Luisa Cordova (Golden Galapagos)"]

# --- automation (see engine/DEPLOYMENT.md) --------------------------------
# SECRETS LIVE IN .env (gitignored), NOT here. Values in .env override these
# and are never committed. Base/table below are non-secret IDs kept as defaults.
site_id: galapagosislands-travel-v1
airtable_base: "appNkUL50eF601ejN"   # Content Production OS — GalapagosIslands.travel
airtable_table: "tblUgxSGGfeJIL5GD"  # Pages Master
airtable_pat: ""            # → set AIRTABLE_PAT in .env (airtable.com/create/tokens: data.records:read+write, schema.bases:read on this base)
n8n_base_url: ""            # → set N8N_BASE_URL in .env (blank = Claude-Code-only mode, no n8n)
n8n_intake_webhook: ""      # → set N8N_INTAKE_WEBHOOK in .env
n8n_api_key: ""             # → set N8N_API_KEY in .env
n8n_poll_minutes: 5

# --- pipeline contract (DO NOT CHANGE — shared across all sites) ----------
status_field: Status
status_values: [Backlog, Scoring, Brief Ready, Drafting, Truth Check, Humanizing, Polishing, Auditor Review, Editor Review, Ready to Publish, Published, Needs Attention]
```

---

## Hard entity rules (brand-agnostic; enforced by ENTITY_RULES.md)

- **Domain** is always `{{DOMAIN}}`. Never write `galapagosislands.com` in links, emails, or citations.
- **Brand name**: refer to the site as `{{BRAND}}` (spoken form `{{BRAND_ALT}}`). Never "Galapagos Travel Center".
- **Editorial independence**: an independent editorial guide, NEVER a single-operator marketing vehicle.
- **No operator favoritism**: name vessels/operators factually and comparatively; never favor one operator; luxury is judged on the vessel's full experience, not which islands it visits (see HARD TRUTHS).
- **Guardian of Truth**: every fact traces to `MASTER_FACTS_FILE`, `GALAPAGOS_FACTS_ADDENDUM.md`, or the linked source-of-truth data; no uncited numbers, no rounded marketing claims.
- **Conversion**: primary CTA is `{{PRIMARY_CTA}}` (a lead/enquiry); never instant "Book Now".
- **HARD TRUTHS** (timing/seasonality and islands/cruises/luxury) in `GALAPAGOS_FACTS_ADDENDUM.md` §0 always apply.

## Fork note
To clone for another brand: edit the BRAND BLOCK above (and the automation values).
Keep `status_values` identical. Do not edit `engine/` logic. The source-of-truth,
guardrails, and fact files are brand-neutral and resolve the `{{TOKENS}}` at load time.
