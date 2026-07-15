# Informational / Planning **Guide Page** — Template Spec

**A section-by-section template builder for informational Galápagos guide pages** —
the "how much does it cost", "best time to visit", "what to pack", "entry
requirements", "cruise vs land" style pages. These are *awareness/consideration*
pages whose job is to be the clearest, most extractable answer on the topic and
hand a warm reader to a specialist.

> Companion files: `GUIDE_PAGE_SAMPLE.galapagos-budget.html` (a filled reference
> build — the "Daily Budget" page) and `GUIDE_PAGE_TEMPLATE.blank.html` (empty
> skeleton with `data-slot`s + JSON-LD scaffolding). Shared design tokens,
> readability rules, and the anti-pattern checklist are inherited from
> `TEMPLATE-SPEC.md` §"The design system", §"Readability rules", §"Anti-pattern
> checklist" — do not re-specify them here; this file only defines what is
> **guide-specific**.

**Provenance (honest):** the design/readability system is inherited from the
HUB `TEMPLATE-SPEC.md` (which came from a real 10-page SERP teardown for
"galapagos cruise"). This guide-page section order + schema profile is adapted
from that design system plus standard informational-guide / AI-Overview
extraction best practice — **not** a separate teardown. Re-run the teardown
method on the guide's target query when you want it evidence-locked (see
"Per-topic hooks").

---

## What makes a GUIDE page different from a HUB page

| | HUB (pillar landing) | **GUIDE (this spec)** |
|---|---|---|
| Intent | commercial, "find/compare cruises" | informational, "answer my question" |
| Funnel | consideration → decision | **awareness → consideration** |
| Core unit | Featured Itineraries (conversion cards) | **Answer box + data table + FAQ** |
| Primary schema | ItemList + Offer + Review | **Article + FAQPage + BreadcrumbList** |
| CTA intensity | strong, repeated PRIMARY | **one soft PRIMARY**, late; help-first |
| Word target | 1,800–2,800 | **1,200–2,000** (answer-dense, no padding) |

The guide page **must not** turn into a sales page. It earns the click to a
specialist by being genuinely useful first. One primary CTA, placed after the
value is delivered.

---

## Meta & head (required on every guide build)

- **`<title>` (Meta Title):** front-load the exact query + a number/qualifier +
  brand. 50–60 chars. e.g. `Galápagos Trip Cost: Daily Budget Breakdown (2026)`.
- **`<meta name="description">`:** 140–160 chars, answer-first, contains the
  headline figure/answer so it can win the snippet. No hype words.
- **Canonical**, **OpenGraph** (`og:title`/`og:description`/`og:image`),
  **`<meta name="robots" content="index,follow">`**.
- **One `<h1>`** — the question in natural language (matches the title intent,
  not identical). Then a **strict heading tree**: `h2` per major section, `h3`
  for sub-points and every FAQ question. Never skip a level; never two `h1`.

---

## Canonical section order (guide page)

The **Words**, **AIO**, and **Schema** columns are the operative build instructions.

| # | Section | Content type | Words | AIO block | Schema |
|---|---------|--------------|------:|-----------|--------|
| 0 | Breadcrumb | nav | — | — | `BreadcrumbList` |
| 1 | **H1 + dateline + author/reviewer byline** | title + trust line | 15–30 | — | `Article` (headline, author, datePublished, publisher) |
| 2 | **Answer Box / TL;DR** (the direct answer, first screen) | callout box: 40–60-word answer + 3–5 key figures as a bullet/stat row | 60–110 | **✅ primary extractable answer** (`speakable`) | `Article`/`speakable` |
| 3 | **On-page anchor sub-nav** (sticky) | jump-links to each H2 | — | — | — |
| 4 | **Body sections** (3–6 `h2`s answering the sub-questions) | short prose (≤60-word paras) + at least one **table** or **card row** per screen | 600–1,100 | question-form H2s; enumerable facts in tables/lists | — |
| 5 | **Comparison / cost table** (the data spine of the page) | responsive `<table>` with a caption | 60–140 | **✅ table = strong AIO/featured-snippet target** | optional `Table`/`Dataset` |
| 6 | **Key takeaways** (scannable recap) | 4–6 bullet callout | 60–100 | **✅ list snippet** | — |
| 7 | **FAQ** (6–10 Q&A) | question-form `h3` accordions, 40–60-word answers, visible on-page | 300–600 | **✅ biggest AIO win** | `FAQPage` |
| 8 | **Related guides** (internal links) | 3–6 link cards to sibling guides/hub | 20–40 | — | — |
| 9 | **Soft conversion band** | one PRIMARY CTA + human reassurance, help-first | 30–60 | — | — |

**Rule:** every ~150–200 words, break prose with a table, list, stat row, or
callout (inherited readability rule). A guide that is a wall of prose fails the
Auditor's Part F (Guardian of Design).

---

## AIO / GEO optimization (what "AIO optimized" means here — make it checkable)

A guide page is judged on **extractability**. Ship all of these:

1. **Answer Box (§2)** — the page's headline answer in **40–60 words**, first
   screen, in a visually distinct box, wrapped so it's `speakable`. This is the
   block most likely to be lifted into an AI Overview / featured snippet.
2. **Question-form headings** — H2/H3 phrased as the real search/PAA question,
   not slogans ("How much does a Galápagos trip cost per day?" not "Costs").
3. **Concrete extractable facts** — every claimable number (from-price,
   day-count, park fee, %, month) stated atomically, ideally in a **table** or
   a **stat row**, once, unrounded-for-marketing.
4. **FAQPage schema (§7)** whose answers **byte-match** the visible FAQ text
   (never let schema and page drift — one source).
5. **`speakable` SpecdProperty** on the answer box + FAQ for voice surfaces.
6. **`Article` schema** with real `author`, `reviewedBy` (if a contributor
   reviewed), `datePublished`/`dateModified`, and `publisher` = {{BRAND}}.

**AIO Block Count target for a guide = ≥ 4** (answer box, table, key-takeaways
list, FAQ). Record it in Airtable `AIO Block Count Target` / confirm in
`AIO Extractable Block Count`.

---

## Schema profile (guide page) — generate server-side from the same content

| Schema | Required | Notes |
|--------|:---:|-------|
| `BreadcrumbList` | ✅ | Home → Pillar → This guide |
| `Article` (or `FAQPage`+`Article`) | ✅ | headline, image, author(Person), publisher(Organization {{BRAND}}, logo), datePublished, dateModified, mainEntityOfPage |
| `FAQPage` | ✅ | 6–10 Q&A, answers mirror visible copy |
| `speakable` | ✅ | CSS-selector pointer to `.answer-box` and `.faq` |
| `HowTo` | ⛔/opt | only for genuine step processes (e.g. "how to get to the Galápagos") |
| `Table`/`Dataset` | opt | for the cost/comparison table |

⚠️ **Never** attach `Review`/`AggregateRating` to a guide page unless it reviews
a specific product with genuine reviews — fabricated rating schema risks a
manual action (same gate as the HUB `reviews` repeater).

---

## UX features (guide page) — the "actions" that must run

These are the polish features the Auditor Part E + G check. A guide build is
**not done** until each is present or explicitly N/A:

- [ ] **Sticky on-page anchor sub-nav** under the H1 (strongest anti-bounce signal).
- [ ] **Answer box** styled distinctly (border/tint), first screen, above the fold.
- [ ] **At least one data table** (cost/comparison) with a `<caption>` + scrollable on mobile.
- [ ] **Stat row / key-figures strip** near the top (the 3–5 numbers a skimmer wants).
- [ ] **Key-takeaways callout** before the FAQ.
- [ ] **FAQ as real accordions** (`<details>`/`<summary>` or ARIA), answers visible to crawlers.
- [ ] **Author/reviewer byline** with a bio link (E-E-A-T; feeds `Article.author`).
- [ ] **One primary CTA**, help-first ("Talk to a Galápagos Specialist"), placed **after** the value — never a hero-blocking modal, never "Book Now" on an awareness page.
- [ ] **Related-guides internal links** (≥3) to sibling guides + the pillar hub.
- [ ] **Responsive, WCAG-AA, lazy-loaded images, ≤ a handful of images** (guides are text-first).

---

## Per-topic hooks (what changes per guide, re-authored not templated)

The authored layer (headings, answer copy, FAQ set, framing) is knowledge and is
hard-coded per guide. The inventory/brand layer stays ACF (see
`ACF-FIELD-MAP.md` two-layer model). Per guide, re-author:

| Hook | Example (budget guide) | Re-pull per guide |
|------|------------------------|-------------------|
| Target query / H1 | "how much does a Galápagos trip cost per day" | the exact PAA query |
| Answer-box figure | "$250–$400 (budget) … $1,000–$2,500+/day (yacht)" | the headline number/range |
| Data table | cost table, 3 travel styles | the guide's core comparison |
| FAQ set | 6 cost PAA questions | People-Also-Ask for this query |
| HARD TRUTHS applied | HT-1 timing, HT-2 islands/luxury | always both, where relevant |

---

## Guide-page acceptance gate (run before advancing past Auditor Review)

Fail the build if any is false:

- [ ] `<title>` 50–60 chars, query-first; `<meta description>` 140–160, answer-first.
- [ ] Exactly one `<h1>`; clean `h2`/`h3` tree; question-form headings.
- [ ] Answer box present, 40–60 words, first screen.
- [ ] ≥1 data table + key-takeaways list + ≥6-question FAQ.
- [ ] JSON-LD: BreadcrumbList + Article + FAQPage, all valid in Rich Results Test, **mirroring visible content**.
- [ ] AIO Block Count ≥ 4; `speakable` present.
- [ ] Every figure sourced or `[VERIFY]`; HARD TRUTHS honored (no "best" without a what-for; luxury = the yacht; only Fernandina + W Isabela need 5-day+).
- [ ] One primary CTA, help-first, late; no hero modal; no fake scarcity.
- [ ] Banned words / clichés absent; answer-first; paras ≤60 words with a visual break every 150–200 words.
