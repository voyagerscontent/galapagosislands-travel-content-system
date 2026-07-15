# Brand Style Guide — LLM Writer Guardrail Tool

A **brand-agnostic** tool that produces a hard-coded guardrail to keep an LLM content writer strictly on-brand — and optimised for both Google SERPs and LLM/AI-Overview visibility.

The tool has two parts:
1. **A repeatable assessment method** — scrape how a set of competitor/reference brands present themselves, and distil the brand factors that drive visibility.
2. **A fillable input template** (`brand-input-template.yaml`) — a brand enters its unique characteristics; the completed file becomes the writer's hard constraints.

> The reference set changes for each brand assessment. This repo's first worked example is the **Galápagos expedition-cruise** set.

## How it works (the pipeline)

```
sites list ─▶ scrape About/Our-Story + home + category page (Zyte)
           ─▶ extract clean text + metadata
           ─▶ profile each brand (fixed schema)
           ─▶ synthesise cross-brand factors  ──▶ defines the template fields
           ─▶ brand fills brand-input-template.yaml
           ─▶ template injected into the LLM writer as guardrails
```

## Files

| File | What it is |
|------|------------|
| **`brand-input-template.yaml`** | **The deliverable.** Brand-agnostic, fillable guardrail. Fill once per brand; inject into the writer. |
| **`examples/ecoventura.filled.yaml`** | A completed example (sourced from real scraped copy) showing what "good" looks like. |
| `brands.json` | The reference site list for this assessment (9 Galápagos brands). |
| `_pass1_tasks.json`, `_pass2_tasks.json` | Scrape task manifests (homepages → discovered About URLs). |

Research artifacts live under `~/.scrape/.work/brand-styleguide/`:
- `pages/<brand>/{home,about1,about2,provided}/` — raw + rendered HTML + screenshots
- `extracted/<brand>.json` — cleaned text + metadata
- `profiles/<brand>.json` — per-brand essence/positioning + SERP/LLM analysis
- `synthesis.json` — the cross-brand factor model + SERP/LLM factor map

## What the assessment found (Galápagos set, 9 brands)

The brands studied: galapagosislands.com, galapatours, aquaexpeditions, gogalapagos, ecoventura, mundyadventures, tauck, travelhx (HX), oceanicsociety.

**Five findings that shaped the template:**

1. **Concrete facts win; vague superlatives lose.** The strongest SERP/LLM performers anchor identity in dated, quantified, attributable facts (founded 1969; first to ban heavy fuel oils 2008; only 82 approved ships; 28-year award streak). The weakest signal is "#1 / best / world-class" with no basis. → template forces `proof_points` to be concrete and adds a `superlatives_require_proof` rule.

2. **Everyone uses the same clichés** — "journey of a lifetime", "Enchanted Islands", "living laboratory of evolution". They create sameness. Differentiation comes only from a brand's own proof + a defensible claim. → `cliche_blocklist` + `differentiation_claim`.

3. **Authority rests on six proof bases:** heritage, ownership, inventory breadth/independence, named experts, certifications, quantified scale/impact. Archetype decides which are credible. → `authority_basis`, `archetype`.

4. **E-E-A-T is brand presentation:** named founders/experts/board (Sylvia Earle, named specialists, named chef), dated heritage, third-party certifications (Relais & Châteaux, TourCert, 501c3), and transparency (published financials). These are exactly what LLMs cite. → `named_experts`, `certifications`, `transparency_artifacts`.

5. **A defensible "first/only/oldest/most" claim is the #1 brand asset** because it becomes a brand-attributable fact in AI answers. → `differentiation_claim`.

Plus: sustainability must be **evidenced or omitted** (greenwashing reads as a negative); and keep cookie/UI/jargon out of body copy. See `synthesis.json` for the full factor map.

## Use it for a new brand

1. Copy `brand-input-template.yaml` → `examples/<brand>.filled.yaml`.
2. Fill every field. Make `proof_points` concrete; write a real `differentiation_claim`; list `banned_words` and `cliche_blocklist`.
3. Add a `content_types` block (with `avoid` list) for each content type you'll generate.
4. Inject the filled YAML into your LLM writer's system prompt as hard constraints.

## Run a new reference assessment (different brands)

1. Put the new site list in `brands.json`.
2. Scrape: `set -a; source ~/downloads/zyte-keys.txt; set +a` then run `~/.scrape/.tools/download.py` with a tasks manifest (homepages first, then discovered About URLs — see `_pass1/_pass2_tasks.json`).
3. Extract → profile → synthesise (same schema as `profiles/` + `synthesis.json`).
4. The synthesis confirms/extends the template fields for that industry.

## Notes & limits

- Scrape used Zyte (rendered HTML + screenshots); 9/9 brands captured. One brand (HX) has no standard About page — its sustainability page was used as the brand-values source.
- Profiles are grounded strictly in scraped copy; claims a brand makes about itself are recorded as *claims*, not verified facts. Verify before publishing.
