# Seed Page Briefs — {{DOMAIN}} ecosystem

Starter backlog. Each brief carries the sub-step A/B outputs so Drafting can run immediately. Load these as Airtable records (Status = Backlog).

---
### BRIEF 1 — Hub: "Galápagos Cruises: How to Choose + Ship Types"
- url: `/galapagos-cruises`
- page_type: hub page (TEMPLATE-SPEC hub blueprint)
- funnel_stage: consideration
- primary_persona: first_timer · secondary: luxury_seeker, family, wildlife_lover
- primary_cta: "Talk to a Galápagos Specialist" · secondary: "Download the Free Galápagos Guide (PDF)"
- objections_to_preempt: choosing_wrong, hidden_fees, crowds, solo_penalty, accessibility
- facts: tier price ranges + park fee (MASTER_FACTS); vessel tiers (galapagos_ships.xlsx); ratings (ship-data)
- schema: ItemList+Offer, FAQPage, Breadcrumb

### BRIEF 2 — Vessel profile: "<Vessel> — Specs, Ratings & Who It Suits"
- url: `/ships/<vessel-slug>`
- page_type: vessel/operator profile
- funnel_stage: consideration · primary_persona: luxury_seeker · secondary: family, wildlife_lover
- primary_cta: "Talk to a Galápagos Specialist" · secondary: "Compare Cruises"
- objections_to_preempt: choosing_wrong, crowds, hidden_fees
- facts: specs (galapagos_ships.xlsx/ships.xlsx); ECO/VALUE/WOW/ITINERARY rank (ship-data); itinerary sites
- rule: factual, distinct per vessel; mark "VERIFIED ACTIVE 2026"; no operator favoritism

### BRIEF 3 — Guide: "Best Time to Visit the Galápagos"
- url: `/best-time-to-visit`
- page_type: guide · funnel_stage: awareness · primary_persona: first_timer · secondary: wildlife_lover, diver_snorkeler
- primary_cta: "Download the Free Galápagos Guide (PDF)" · secondary: "Talk to a Galápagos Specialist"
- objections_to_preempt: trust
- facts: seasons + wildlife calendar + visitor-site access (source-of-truth)
- schema: FAQPage

### BRIEF 4 — Comparison: "Galápagos Cruise vs Land-Based Tour"
- url: `/cruise-vs-land-based`
- page_type: comparison · funnel_stage: consideration · primary_persona: first_timer
- primary_cta: "Talk to a Galápagos Specialist"
- objections_to_preempt: choosing_wrong, hidden_fees
- facts: trip-type matrix + site-access (galapagos_source_of_truth.xlsx)
- rule: honest "it depends"; show the downside of each option

### BRIEF 5 — FAQ hub: "Galápagos Travel FAQs"
- url: `/faq`
- page_type: FAQ · funnel_stage: decision · primary_persona: first_timer · secondary: family, solo
- primary_cta: "Talk to a Galápagos Specialist" · secondary: human fallback (chat/call)
- objections_to_preempt: safety, cancellation, weather_flight, hidden_fees, trust
- facts: park fee, transit card, flights, insurance, ages (MASTER_FACTS)
- schema: FAQPage (answers 40–60 words, answer-first)
