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
- Many outer/uninhabited sites (Fernandina, Genovesa, parts of Isabela, Española) are reachable only by liveaboard cruise; day-trips from inhabited islands reach ~1/3 of sites. Darwin & Wolf are liveaboard-dive-only.
- Guides are **GNPS-certified**; landings are by panga/Zodiac (wet or dry); strict wildlife-distance and biosecurity rules apply.

## One-time rebrand applied to this source-of-truth (this run)
The source-of-truth was rebuilt from a galapagosislands.com scrape. For this site it has been rewritten:
- `galapagosislands.com` → **{{DOMAIN}}** (1,700 replacements)
- `{{BRAND}}` → **"{{BRAND}}"** or **"{{BRAND}}"** (varied; 1,105 replacements)
Treat the rebranded data as authoritative for {{DOMAIN}}. The original builders/data are untouched and serve other sites.

## Known data caveats (do not repeat as fact)
- San Cristóbal area appears as "1.9 sq mi" in the source (a source typo; actual ≈215 sq mi). Do not cite the typo.
- Some vessel lengths are feet-only (metric null); some scraped specs were blanked/flagged by the ratings validator — a blanked spec is unknown, not zero. Missing-motor vessels are auto-downgraded in the ratings.
