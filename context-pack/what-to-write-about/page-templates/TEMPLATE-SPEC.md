# Galápagos Cruise Hub — Landing Page Template Spec

**An evidence-based, section-by-section template builder for expedition-cruise hub pages.**
Derived from a teardown of the **10 pages ranking in Google's top 10 for "galapagos cruise"** (captured 2026‑06‑23 via Zyte: rendered HTML + full‑page screenshots → 10 per‑page design/UX teardowns → 1 design‑synthesis + 1 UX‑synthesis pass).

> This is the writer's & designer's playbook. It tells you **what each section is for, what content type to use, how much to write, where it goes, which schema to attach, and what to avoid** — all grounded in what the ranking pages actually do. The companion `index.html` + `styles.css` implement this skeleton with labelled content slots.

---

## The corpus (who we learned from)

| # | Domain | Archetype | Words | Schema highlights | One-line takeaway |
|---|--------|-----------|------:|-------------------|-------------------|
| 1 | celebritycruises.com | Brand cruise line | 3,587 | *(none)* | Icon "what's included" row; "A Typical Day" timeline; package‑comparison accordion |
| 2 | aquaexpeditions.com | Brand cruise line | 6,999 | Article | In‑page anchor nav; audience self‑qualification cards; best‑time weather card |
| 3 | mundyadventures.co.uk | Editorial listicle | 2,062 | BlogPosting, Breadcrumb | Question‑form Q&A headings; ranked 1‑5 by traveller type; free‑guide lead magnet |
| 4 | galapatours.com | Aggregator | 1,279 | *(none)* | Leanest page yet ranks; "100,000+ travellers" trust band; 3‑step "how to choose" |
| 5 | ecoventura.com | Brand cruise line | 7,611 | Breadcrumb, Organization, Image | Hero availability widget; tabbed "Life On Board"; press‑logo trust band |
| 6 | tauck.com | Tour operator | 5,553 | OfferCatalog, TravelAgency | Serif video hero; filterable cards + Compare; interactive route map |
| 7 | liveaboard.com | Aggregator | 7,828 | Product | **"712 verified reviews" in hero**; price+rating+count cards; trust‑badge strip |
| 8 | silversea.com | Brand cruise line | 2,963 | ItemList, TouristDestination | Filterable "Find your cruise" finder; named naturalist guides |
| 9 | oceanicsociety.org | NGO / conservation | 1,803 | ItemList | Trip‑fact band under hero; left anchor sidebar; conservation‑impact stats |
| 10 | metropolitan-touring.com | Brand cruise line | 3,243 | **FAQPage + ItemList + Breadcrumb + VideoObject + Place + Org** | **The cleanest overall template** — hero pills + anchor nav + FAQ schema |

### Five headline findings

1. **Word count does *not* correlate with rank.** The 1,279‑word page (#4) and the 7,828‑word page (#7) both rank top‑10. → **Target 1,800–2,800 words**; push overflow into accordions/cards, not longer prose.
2. **Structured data is the single biggest open opportunity.** Only **1 of 10** uses **FAQPage** schema; **0 of 10** mark up **reviews**. A new entrant can out‑markup the entire SERP.
3. **In‑page anchor sub‑nav (under the hero) is the strongest "quality" signal.** Present on the best‑organised pages (#2, #6, #9, #10); absent on the scroll‑punishing ones (#1, #7, #8).
4. **Hero‑blocking modals are the most common mistake** (6/10). Never cover the hero with a cookie/newsletter overlay.
5. **CTA overload kills focus.** Several pages stack 4–5 competing CTAs (and 100–194 buttons). Use **one** dominant CTA, reused verbatim.

---

## The design system (visual language)

| Token | Decision | Evidence |
|-------|----------|----------|
| **Grid** | 12‑col responsive; prose in a single centred column, **line measure capped ~680–720px** inside a ~1200px container; 3‑up card grids; 4‑up icon rows; cards → 1‑up on mobile | airy density shared by 8/10; #7's dense layout scans worst |
| **Type** | **Editorial serif (or letter‑spaced uppercase) headings** + **light humanist sans body**; H1 40–52px, H2 30–34px, H3 22–24px, **body 17–18px / line‑height 1.6** | the "premium travel" signature on #1,2,5,6,8,9,10 |
| **Colour** | **White/cream base** + light‑grey alternating bands + charcoal/navy text + **ONE warm gold/amber accent reserved only for CTAs**; deep navy/teal for trust & footer bands | #10 & #8 converge on navy + gold |
| **Imagery** | ~50% wildlife · 35% real ship/cabin · 15% lifestyle; uniform card crops; **hard‑cap < 60 images**, lazy‑load below the fold, responsive `<picture>` | #10 = 17 imgs (disciplined) vs #5 = 816, #7 = 150 (gray placeholders) |
| **Rhythm** | Alternate full‑bleed photo band → light prose+bullets → card grid → image/text band (flip side each time) → icon strip → tabbed/accordion → proof band; alternate bg fill every section | #1,2,5,6,8 storytelling cadence |
| **Density** | **Airy.** Generous whitespace; never a text wall | only #7 is "dense" and it's the worst‑scanning page |

---

## Canonical section order (merged design + UX)

The number is the page order. **CTA**, **Schema**, and **Words** columns are the operative build instructions.

| # | Section | Content type | Words | CTA | Schema |
|---|---------|--------------|------:|-----|--------|
| 0 | Sticky global nav + breadcrumb | sticky bar | — | persistent **PRIMARY** | `BreadcrumbList` |
| 1 | **Hero** (H1 + subhead + **rating/review count** + **trip‑fact strip** + quick‑filter pills) | full‑bleed photo + 1 CTA | 25–45 | **PRIMARY** | `WebPage`,`ImageObject`,`Organization` |
| 2 | **In‑page anchor sub‑nav** (sticky) | jump‑links | — | sticky PRIMARY pinned | — |
| 3 | Quantified‑trust + guarantee strip | icon row | 20–40 | — | `AggregateRating` |
| 4 | What to Expect / intro desire copy | prose (2 short paras) + 1 image | 120–180 | — | — |
| 5 | Why Galápagos + **What's Included** | short prose + **icon‑led inclusions** | 180–300 | — | — |
| 6 | **"Great cruise for"** (audience self‑qualification) | cards (nature/families/divers/luxury/solo) | 80–140 | card links | — |
| 7 | **How to Choose the Best Galápagos Cruise** | numbered decision guide | 200–300 | — | *(question‑form H2)* |
| 8 | **Best Time to Visit** (wildlife/weather calendar) | prose + month/wildlife card | 180–280 | **secondary: Free Guide** | — |
| 9 | **Featured Itineraries** (core conversion unit) | **cards: price‑from · days · route · rating · View** | 120–220 | per‑card *View* + repeat PRIMARY | **`ItemList` + `Trip`/`Product` + `Offer`** |
| 10 | Ships / Fleet | cards or **tabs by vessel** | 120–200 | View Ship | — |
| 11 | Naturalist Guides / Expertise | profile cards (photo, name, creds) | 80–150 | — | — |
| 12 | Conservation & Sustainability | prose + impact stat counters | 80–140 | — | — |
| 13 | (optional) Map of routes | interactive/illustrated map | light | — | — |
| 14 | **Reviews / Testimonials** *(placed right before the ask)* | named cards w/ stars + count | 100–160 | — | **`Review` + `AggregateRating`** |
| 15 | Why Travel With Us + **Pre‑Booking Checklist** | proof bullets + checklist | 150–260 | — | — |
| 16 | **FAQ** (8–12 Q&A) | **question accordions, 40–60 word answers** | 400–700 | — | **`FAQPage`** |
| 17 | **Closing conversion band** | one CTA + human reassurance + lead form | 30–60 | **PRIMARY (single, no stacking)** | `VideoObject` if video |
| 18 | Footer | link grid, navy/teal | light | quiet newsletter | — |

---

## Section-by-section writer brief

Each entry: **Purpose · Build · Write · Avoid · Steal‑from.**

### 1 · Hero
- **Purpose:** Orient, qualify and convert intent in one screen; surface social proof immediately.
- **Build:** Full‑bleed wildlife/aerial photo at **60–75vh** (marine iguana, giant tortoise, sea lion, or Bartolomé/Pinnacle Rock). Short Title‑Case H1 + one ≤12‑word subhead. **One** primary CTA + a quieter outline secondary. A slim **trip‑fact micro‑band** (`From $X · 4–8 days · Year‑round departures`) and **quick‑filter pills** (by vessel / traveller type / length). Aggregate rating + review count in the subhead.
- **Write (25–45 words):** H1 names place+benefit ("Galápagos Expedition Cruises"); subhead ties biodiversity + experience.
- **Avoid:** ❌ Any modal over the hero on load (the #1 competitor mistake). ❌ Heavy multi‑field search form. ❌ No‑headline hero (#3).
- **Steal:** Hero review‑count proof (#7 "712 verified reviews"), trip‑fact strip (#9), vessel pills (#10).

### 2 · In‑page anchor sub‑nav (sticky)
- **Purpose:** Self‑routing on a long page → the strongest anti‑bounce device in the set.
- **Build:** Horizontal jump bar docked under the hero, becomes sticky on scroll, with the PRIMARY CTA pinned to its right. Items: **Itineraries · Best Time · Ships · Reviews · FAQ** (+ Overview, What's Included).
- **Steal:** #2, #6, #9, #10.

### 3 · Quantified‑trust + guarantee strip
- **Purpose:** Early credibility before any ask.
- **Build:** Thin icon row: *years operating · travellers served · review count · best‑price guarantee · certified guides*. Attach `AggregateRating`.
- **Steal:** #4 ("100,000+ travellers"), #7 badges.

### 4 · What to Expect (intro desire copy)
- **Build:** Two short paragraphs (≤60 words each) + one supporting image, image‑left. Constrained column.
- **Write (120–180):** Lead with the payoff sentence (inverted pyramid). Set relevance and tone.
- **Avoid:** ❌ Text wall.

### 5 · Why Galápagos + What's Included
- **Build:** Short prose + a **4–6 tile icon row** (flights, shore excursions, naturalist guides, meals, Wi‑Fi, gear).
- **Write (180–300):** Answer "what do I get" at a glance; justify the price.
- **Steal:** Icon inclusions (#1, #5, #10).

### 6 · "Great cruise for" (audience self‑qualification)
- **Build:** 3–5 cards routing visitors: *Nature lovers · Families · Divers/Snorkelers · Luxury · Solo*.
- **Write (80–140):** One‑line promise per card + link.
- **Steal:** #2.

### 7 · How to Choose the Best Galápagos Cruise
- **Purpose:** Reduce decision paralysis + earn People‑Also‑Ask.
- **Build:** Numbered decision guide / 3‑step process. **Question‑form H2.**
- **Write (200–300):** Cover ship class, itinerary length, east‑vs‑west islands, budget.
- **Steal:** #10, #4.

### 8 · Best Time to Visit
- **Build:** Prose + a compact **month / weather / wildlife calendar card**. Place the **secondary lead‑magnet CTA** ("Download the Free Galápagos Guide") here.
- **Write (180–280):** Lead with a direct answer ("The Galápagos is a year‑round destination; the warm season runs Dec–May…").
- **Steal:** #2 weather card.

### 9 · Featured Itineraries  ← **core conversion unit**
- **Build:** 3‑up **comparison cards**, each exposing **price‑from · duration · route zone · rating · "View Itinerary."** Repeat the PRIMARY CTA below the grid. Optionally a **tabbed browser by vessel/type** beneath.
- **Write (120–220):** Card blurbs only; **unique descriptive heading per itinerary** (never duplicate — #8 repeated "San Cristóbal to San Cristóbal" 30×).
- **Schema:** `ItemList` → each card a `Trip`/`Product` with `Offer` (price, priceCurrency, availability).
- **Steal:** #6, #7, #8, #10.

### 10 · Ships / Fleet
- **Build:** Cards or **tabs by vessel**; real ship + cabin photography. Optional tabbed "Life On Board" (Fleet/Staterooms/Excursions/Cuisine).
- **Steal:** #5 tabs, #10 tabbed itineraries.

### 11 · Naturalist Guides / Expertise
- **Build:** Profile cards — photo, name, credentials ("Galápagos National Park‑certified"). The genre's #1 expertise signal.
- **Steal:** #5, #8, #9, #10.

### 12 · Conservation & Sustainability
- **Build:** Short prose + **impact stat counters** (e.g. trash removed, trees, grant dollars; carbon‑neutral; eco‑cert).
- **Steal:** #9 per‑traveller impact, #4 TourCert.

### 13 · Map of routes *(optional, differentiating)*
- **Build:** Interactive/illustrated route map tied to a featured bookable itinerary.
- **Steal:** #6.

### 14 · Reviews / Testimonials  ← **place immediately before the final CTA**
- **Build:** Named‑reviewer cards with **stars + visible count**; surface an aggregate rating.
- **Schema:** `Review` + `AggregateRating` (**no competitor does this — rich‑result stars up for grabs**).
- **Steal:** #7, #4.

### 15 · Why Travel With Us + Pre‑Booking Checklist
- **Build:** Proof bullets (years, awards, press logos, doctor‑on‑board) + a **checklist** (passport, travel insurance, park fees) that pre‑empts objections.
- **Steal:** #10 checklist.

### 16 · FAQ  ← **biggest AIO win**
- **Build:** Visible **accordion** of **8–12 question‑form H3s**, each a verbatim People‑Also‑Ask query. Back with **FAQPage schema** (answers must be visible on‑page).
- **Write (40–60 words/answer):** Lead with a one‑sentence direct answer, then 1–2 support sentences; atomic, no "as above." Suggested set: *How much does a Galápagos cruise cost? · Best month to go? · How many days do you need? · How to choose? · Cruise vs land‑based tour? · What to pack? · Are they worth it? · Family‑friendly?*
- **Steal:** #10 (only page with FAQPage schema); #7 question set.

### 17 · Closing conversion band
- **Build:** **One** dominant CTA + short lead form + human reassurance ("Talk to an Expert That's Sailed Aboard"). One warm lifestyle image.
- **Avoid:** ❌ Stacking Book/Quote/Subscribe/Start‑Planning (the #2/#10 mistake).
- **Steal:** #10 human framing, #9 lead form.

### 18 · Footer
- **Build:** Deep navy/teal; sitemap, ship index, contact, quiet newsletter signup.

---

## Conversion & CTA rules

- **Primary goal:** ENQUIRE / qualified lead (Galápagos is a $4k–10k+, date/cabin‑constrained purchase; 8/10 competitors are lead‑first). Surface **live availability** only where you hold inventory data.
- **One** primary CTA label, reused **verbatim** everywhere: **"Check Availability & Dates"** *(inventory)* or **"Talk to a Galápagos Expert"** *(lead)*.
- **One** secondary: **"Download the Free Galápagos Cruise Guide (PDF)"** (mid‑page, once).
- **Per‑card** "View Itinerary" is navigational, not a competing brand CTA.
- **Budget:** ≤3 primary instances + 1 sticky + 1 lead magnet. Avoid the 101‑button (#1) / 194‑button (#7) sprawl.

## Readability rules (keep text light on the eye)

- Paragraphs **≤ 60 words**; break every 2–3 paragraphs with a bullet list, card, icon row, accordion or image.
- Sentences avg **15–20 words**, one idea each; **answer‑first** (inverted pyramid) so the opening line is AI‑Overview‑quotable.
- **Reading level Grade 7–9.** Define expedition terms (zodiac/panga, endemic) inline on first use.
- Line measure **65–75 chars**; body **17–18px / 1.6**; **WCAG AA** contrast (never light‑grey body on white).
- Question‑form subheads every ~150–200 words. Reserve uppercase for short eyebrows/labels only.

## AIO / Schema strategy (the competitive moat)

Implement **all** of these (combined, they out‑markup the entire current top‑10):

1. **`FAQPage`** — only #10 has it. Highest priority.
2. **`ItemList` + `Trip`/`TouristTrip`/`Product` + `Offer`** (price, currency, availability) on itinerary cards.
3. **`AggregateRating` + `Review`** — **none** of the 10 mark up reviews → rich‑result stars open.
4. **`BreadcrumbList`** — cheap hierarchy signal.
5. **`Organization`/`TravelAgency`** (logo, contactPoint, sameAs).
6. **`VideoObject`** for the experiential video; **`ImageObject`** for hero; **`Place`/`TouristDestination`** for the Galápagos entity.

**Answer‑friendly writing:** question‑form headings matching search phrasing (not slogans); concrete extractable facts (from‑prices, day‑counts, best months, species counts, park‑fee figures); atomic 40–60‑word FAQ answers; bullet lists for enumerable answers; an explicit **"Galápagos cruise vs land‑based tour"** block (a strong PAA query nobody owns well).

---

## Anti‑pattern checklist (do **not** ship if any are true)

- [ ] A cookie/newsletter/privacy modal covers the hero on load.
- [ ] More than one primary CTA label, or 4+ competing CTAs.
- [ ] No in‑page anchor nav on a 2,000+‑word page.
- [ ] Visible FAQ but **no FAQPage schema**; reviews present but **no Review/AggregateRating**.
- [ ] Duplicate/near‑identical itinerary or card headings.
- [ ] A prose block longer than ~3 short paragraphs with no visual break.
- [ ] Click‑to‑load video rendering as a black/gray box (use a real poster frame).
- [ ] Off‑topic cross‑sell (other destinations) diluting Galápagos focus.
- [ ] > 60 images / un‑lazy‑loaded media below the fold.
- [ ] Reviews buried in the footer instead of right before the final CTA.

---

*Companion files:* `index.html` (semantic skeleton with labelled `data-slot` content slots, the three nav layers, tabs, accordion FAQ, and all JSON‑LD schema scaffolding) · `styles.css` (the design system above) · `README.md` (how to use). Source evidence lives in `.scrape/.work/google-search/` (per‑page `teardown.json`, `synthesis_design.json`, `synthesis_ux.json`, screenshots).
