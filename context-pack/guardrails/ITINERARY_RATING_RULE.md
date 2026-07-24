# ITINERARY RATING RULE — {{DOMAIN}}

**Context-scoped.** Loads only for itinerary, vessel, tour and cruise-hub pages. Do not load
it for guides, wildlife, island or FAQ pages — it is not relevant there and irrelevant rules
produce padding.

## What this is

The source-of-truth corpus (`galapagos_master.xlsx` → `galapagos_source_of_truth.xlsx`, built
from DPNG visitor-site data, the Charles Darwin Foundation, Galápagos Conservancy and the
Galápagos Conservation Trust) is used to **qualify and optimise the scores we give Galápagos
cruise itineraries**. The scoring lives in:

| File | Factor |
|---|---|
| `ship-data/ITINERARY_rating.xlsx` | itinerary quality / site mix |
| `ship-data/ECO_rating.xlsx` | environmental performance |
| `ship-data/VALUE_rating.xlsx` | value for money |
| `ship-data/WOW_factor.xlsx` | standout experience |
| `source-of-truth/DPNG Site Activities` | which sites an itinerary reaches, and what is permitted there |

## The rule

1. **This is a rule, not copy.** Never paste this file, its mechanics, or its file names into a
   page. See OUTPUT_HYGIENE §1.
2. **It may be written about** — but only when the page is explaining **how itineraries were
   rated**. Then say plainly that the rating draws on visitor-site access data from the
   National Park and the conservation authorities, and that this is **one factor among
   several** (alongside eco performance, value and the onboard experience). Never present it
   as the whole basis of a score.
3. **Ratings are this guide's model output, not absolutes** (GUARDIAN_OF_TRUTH rule 5). Say so,
   and name the factor being cited.
4. **Never invent a score.** If a vessel or itinerary has no rating in the data, it has no
   rating — write `[VERIFY]`, never a guess.
5. **No operator favoritism** (ENTITY_RULES). A rating explains a judgement; it never becomes a
   pitch for one vessel.
6. **HT-2 still governs.** A rating must never imply that the islands an itinerary visits make
   a boat "luxury", nor that a higher-rated itinerary reaches better islands. Only Fernandina
   and west Isabela need a 5-day-or-longer cruise; the shortest cruise is 4 days and can be
   luxury.

## Worked example (tone, not a template)

> Good — explaining the basis:
> "Our itinerary score weighs which visitor sites a route actually reaches, using the National
> Park's site-access data, alongside eco performance, value and the onboard experience. It is
> our own scoring, not an official ranking."

> Bad — reciting the rule:
> "This itinerary was rated using ITINERARY_rating.xlsx and DPNG Site Activities data as one of
> many factors."
