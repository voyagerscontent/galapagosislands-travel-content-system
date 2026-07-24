# MASTER FACTS FILE — {{DOMAIN}}

The single grounding source for facts. The writer may assert ONLY what is here or in the linked source-of-truth data. Anything else is `[VERIFY]`. (Guardian of Truth.)

## Data sources (authoritative — cite the file/sheet inline)
| Need | File (under `context-pack/what-to-write-about/`) | Contents |
|---|---|---|
| Island facts | `source-of-truth/galapagos_island_facts.xlsx`, `island_facts.jsonl` | 11 islands: area, highest point, animals, visitor sites |
| Trip types / site access / content rules / glossary | `source-of-truth/galapagos_source_of_truth.xlsx` | 4 trip-type matrix, DAY-TRIP/LIVEABOARD site access, 106 content rules, glossary |
| Full site content corpus | `source-of-truth/galapagos_master.xlsx`, `galapagos_site_content.xlsx`, `pages.jsonl` | catalog + cleaned body text (rebranded copy) |
| Vessel specs & prices | `source-of-truth/galapagos_ships.xlsx`, `ship-data/ships.xlsx/csv`, `ships.jsonl` | 79 vessels: type, stars, year, length, beam, capacity, cabins, engines, speed, crew, prices |
| Vessel ratings | `ship-data/ECO_rating.xlsx`, `VALUE_rating.xlsx`, `WOW_factor.xlsx`, `ITINERARY_rating.xlsx` | live-formula ECO / VALUE / WOW / ITINERARY scores & ranks (126 boats) |
| Visitor sites & itineraries | `ship-data/visitor_sites.xlsx/csv`, `ship_itineraries.csv`, `itinerary_sites.jsonl` | per-site scores, day-by-day site sequences (256 itineraries) |

## Core stable facts (safe to state; deeper detail lives in the data)
- The Galápagos is an Ecuadorian archipelago ~600 miles (1,000 km) off the South American coast; 13 major islands, ~6 smaller isles, 100+ rocks/islets; >90% national park.
- Year-round destination, two seasons: **warm/wetter Dec–May** (calmer seas, courtship displays) and **cool/dry "garúa" Jun–Nov** (nutrient-rich water, best snorkelling, active seabirds).
- **Galápagos National Park entrance fee: $200** for most foreign adults (since Aug 2024); **INGALA transit control card ~$20**. Both are extra on every cruise.
- Cruises run **4–15 days**, roughly **$2,500–$20,000+ per person** across tiers (budget / first-class expedition / luxury small ship / ultra-premium yacht). Mainland flights (Quito/Guayaquil → Baltra/San Cristóbal) ~$400–$500, ~3 hrs; arrive a day early.

### Per-day costs (the only sourced per-day figures — never invent others)
A per-day figure NOT in this section does not exist. Do not derive one from the aggregate band
above and present it as fact; cite these instead. Both are **our own data** — attribute them as
this guide's own cruise data / advisory estimate, never as a third-party statistic.

- **Cruise, per person per day** — from `source-of-truth/galapagos_master.xlsx` sheet
  **`Cruise Per-Day Rates`**. Across the fleet: **~$445–$2,193/day, median ~$907** (256 price
  points from 58 vessels). By category: 3-star **~$445–$928** (median $640), 4-star
  **~$505–$1,170** (median $825), 5-star **~$520–$2,193** (median $1,189). 2-star has only 4
  data points (~$535–$599) — too thin to quote as a band.
  Basis: cheapest non-charter cabin per advertised duration ÷ duration, 2026/2027 published
  rates; charter (whole-boat) excluded; 12 of 70 priced vessels lack usable price text.
- **Land-based (hotel + day tours), per person per day** — from sheet
  **`Land-Based Per-Day Rates`**: **~$150–$700/day**. Budget hostels + shared day tours at the
  low end through high-end hotels + private guiding at the top. Authority: {{BRAND}} advisory
  data (the guide's own operating knowledge).
- Both ranges **exclude** the $200 park fee, the ~$20 INGALA card and ~$400–$500 mainland
  airfare — those are separate fixed costs, not daily ones.
- **Star category does not track price.** The 5-star median ($1,189) sits above the 4-star
  median ($825), but the 4-star maximum ($1,170) overlaps deep into 5-star territory. Price
  buys the vessel's experience, not a rung on a ladder (see HT-2).
- **Caveat:** the Ships column `Price From Usd Per Day` is **mislabelled** — it holds a whole-trip
  "from" price, not a daily rate. Never cite that column as a per-day figure.
- Many outer/uninhabited sites (Fernandina, Genovesa, parts of Isabela, Española) are reachable only by liveaboard cruise; day-trips from inhabited islands reach ~1/3 of sites. Darwin & Wolf are liveaboard-dive-only.
- Guides are **GNPS-certified**; landings are by panga/Zodiac (wet or dry); strict wildlife-distance and biosecurity rules apply.

## Rebrand applied to this source-of-truth
The corpus carries this site's **pre-rebrand** content: URLs were already on {{DOMAIN}} while the
body text still named the old identity. Those names are a different entity now and must never be
cited (ENTITY_RULES). Rewritten in `galapagos_master.xlsx` (2026-07-16, 476 replacements over 402
cells, `Content Catalog` + `Content Full Text`):
- `GalapagosIslands.com` → **{{BRAND}}**; bare domain → **{{DOMAIN}}**
- `Galapagos Travel Center` → **GIT - {{BRAND}}**; `GTC` → **GIT**
The `Url` column was deliberately left untouched — rewriting slugs such as `join-gtc.html` would
fabricate links that do not resolve. `galapagos_source_of_truth.xlsx` scans clean.
Treat the rebranded data as authoritative for {{DOMAIN}}. The original builders/data are untouched and serve other sites.

## Merged authorities (2026-07-16) — see the `Sources` sheet for provenance
`galapagos_master.xlsx` now carries, alongside the site corpus: **Darwin Foundation** (1,289 pages),
**Galapagos.org** / Galápagos Conservancy (647), **Conservation Trust** (836), the **DPNG** visitor-site
grid (210 sites) plus its legend and per-island/per-activity summaries, and **Island Geography** —
Snell, Stone & Snell (1996), *A Summary of Geographical Characteristics of the Galapagos Islands*,
Journal of Biogeography 23(5): 619–624 (JSTOR 2846050).

## Known data caveats (do not repeat as fact)
- San Cristóbal area appears as "1.9 sq mi" in the source (a source typo; actual ≈215 sq mi). Do not cite the typo.
- Some vessel lengths are feet-only (metric null); some scraped specs were blanked/flagged by the ratings validator — a blanked spec is unknown, not zero. Missing-motor vessels are auto-downgraded in the ratings.
