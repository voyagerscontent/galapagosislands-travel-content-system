# Page-Type Registry — {{DOMAIN}}

Every page on the site belongs to **exactly one page type**. Each type has its own
template (section order, H1/H2 tree, meta rules, AIO blocks, schema profile, UX
features) so writers and the pipeline stay consistent. The Airtable `Page Type`
field must match a `type_id` below, and the Drafting stage loads that type's spec.

**Why per-type templates:** a yacht page and a budget guide answer different jobs,
need different schema (Product/Offer vs Article/FAQPage), and different UX. One
generic template produces inconsistent, under-optimized pages — which is the gap
this registry closes.

## Status legend
✅ built · 🟡 spec only · ⛔ not started

| type_id | Page type | Intent | Primary schema | Template files | Status |
|---------|-----------|--------|----------------|----------------|:---:|
| `hub` | Pillar / category hub (e.g. /galapagos-cruises/) | commercial, compare | ItemList+Offer, FAQPage, Review, Breadcrumb, Org | `TEMPLATE-SPEC.md`, `HUB_PAGE_SAMPLE.galapagos.html`, `HUB_PAGE_TEMPLATE.blank.html`, `ACF-FIELD-MAP.md` | ✅ |
| `guide` | Informational / planning guide (budget, best-time, packing, entry reqs, cruise-vs-land) | awareness→consideration | Article, FAQPage, Breadcrumb, speakable | `GUIDE_PAGE_SPEC.md`, `GUIDE_PAGE_SAMPLE.galapagos-budget.html` | ✅ |
| `island` | Per-island guide (Santa Cruz, Isabela…) | awareness | Article, FAQPage, Place/TouristDestination, Breadcrumb | — | ⛔ |
| `wildlife` | Species / wildlife page (giant tortoise, blue-footed booby…) | awareness, LLM-citation asset | Article, FAQPage, (Taxon-style), Breadcrumb | — | ⛔ |
| `vessel` | Yacht / ship profile (per vessel) | decision | Product+Offer, Review/AggregateRating*, Breadcrumb | — | ⛔ |
| `tour` | Itinerary / tour page (per itinerary) | decision | TouristTrip+Offer, Breadcrumb | — | ⛔ |
| `hotel` | Hotel / lodge page (per property) | decision | Hotel/LodgingBusiness+Offer, Review*, Breadcrumb | — | ⛔ |
| `comparison` | X vs Y (cruise vs land, ship A vs B, class vs class) | consideration | Article, FAQPage, (Table/Dataset), Breadcrumb | — | ⛔ |
| `faq` | Standalone FAQ / single-question page | awareness, AIO | FAQPage/QAPage, Breadcrumb | — | ⛔ |
| `bio` | Author / expert bio page (E-E-A-T) | trust | Person + Organization, Breadcrumb | — | ⛔ |

\* `Review`/`AggregateRating` only with genuine, verifiable reviews (fabricated
rating schema risks a Google manual action).

## Build order (recommended)
1. `guide` ✅ (done — reference for all informational pages)
2. `vessel` + `tour` (highest commercial value; the yacht/itinerary catalog)
3. `island` + `wildlife` (LLM-citation + destination-authority assets)
4. `hotel`, `comparison`, `faq`, `bio`

## How to build a new page-type template (repeatable method)
1. Pick the target query set; if commercial, run the SERP-teardown method from
   `TEMPLATE-SPEC.md` (top-10 → per-page teardown → design + UX synthesis).
2. Write `<TYPE>_PAGE_SPEC.md` — inherit design/readability/anti-patterns from
   `TEMPLATE-SPEC.md`; specify only the type-specific section order, schema
   profile, AIO blocks, and UX feature checklist.
3. Build `<TYPE>_PAGE_SAMPLE.galapagos-*.html` — a filled reference build with
   real authored copy + `{{TOKENS}}` for the inventory layer + JSON-LD generated
   from the same copy.
4. Add the ACF token map (extend `ACF-FIELD-MAP.md`) for the inventory layer.
5. Register here (flip status, list files). Update the Airtable `Page Type`
   single-select options to include the `type_id` if missing.
