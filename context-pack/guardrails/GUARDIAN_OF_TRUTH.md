# GUARDIAN OF TRUTH — {{BRAND}}

Runs at **Truth Check** (and as a constraint during Drafting). The brand's first Editorial Guardian. Brand-neutral: all brand values resolve from `config/SITE_CONFIG.md`.

## HARD TRUTHS (highest priority — never violate)
From `../what-to-write-about/source-of-truth/GALAPAGOS_FACTS_ADDENDUM.md` §0; override any tempting shortcut:
- **Timing (HT-1):** Galápagos is a great year-round destination. Never say a time of year is "better/best/worst" *in general*. Timing is allowed only when tied to a **specific species/event** and says **what it is for** (e.g. waved albatross on Española ~Apr–Dec). One species must never define the whole destination. A stated *preference* is OK **only with a true, specific reason**. Never promise a specific sighting.
- **Islands/cruises/luxury (HT-2):** No island is "better" than another (a preference is OK if explained). An island on an itinerary does **not** make a boat "luxury"; nearly all boats reach nearly all islands. **Luxury depends on the yacht's full experience, not infrastructure or islands visited.** All islands are reachable on a **5-day+** cruise; **only Fernandina & west Isabela** are unreachable on **4-day-or-shorter** programs. The **shortest cruise is 4 days and can be luxury.**
- Fail Truth Check if copy ranks a month or island as generally "best," equates islands-visited with luxury, or claims a sub-4-day itinerary reaches Fernandina/west Isabela.

## Rules
1. **Every fact must trace to a source** in MASTER_FACTS_FILE, GALAPAGOS_FACTS_ADDENDUM.md, or the linked source-of-truth / ship-data files. Tag it inline `[source: <file/sheet>]`.
2. **No invented numbers.** Prices, dates, ratings, capacities, distances, review counts — only from the data. If absent, write `[VERIFY]`, never a guess.
3. **No rounded marketing claims.** "the best", "#1", "world-class", "unbeatable" are off-brand AND unverifiable — banned unless the data carries a cited, attributable basis.
4. **Respect data caveats.** Do not repeat the San Cristóbal area typo; treat blanked vessel specs as unknown, not zero.
5. **Ratings are model outputs, not absolutes.** When citing ECO/VALUE/WOW/ITINERARY ranks, say they are this guide's transparent scoring, and name the factor.
6. **Seasonality/wildlife claims** must match the source-of-truth season + visitor-site data; never promise a specific animal sighting.

## Human enrichment (optional add-ons)
Content tagged `[human: <Contributor>]` (paragraphs, quotes, anecdotes from the intake form) is **human-authored and attributed** — it is exempt from the source-tag requirement. But it must **not contradict** MASTER_FACTS. If a human claim conflicts with the data, mark `[VERIFY]` and escalate; never silently alter or delete the human text.

## Truth Check procedure
- For each factual sentence, confirm a source tag. Untagged factual claims → fail.
- Verify entity rules (see ENTITY_RULES) are satisfied.
- On pass → Humanizing. On fail → record the unsourced claims in `Last Error`, set `Needs Attention` per the state model.
