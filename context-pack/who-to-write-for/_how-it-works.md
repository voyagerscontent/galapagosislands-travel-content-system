# Audience & Conversion Architecture — LLM Writer Guardrail

A **site-agnostic** tool that gives an LLM content writer a hard-coded guardrail for **who it's writing to, where the page sits in the booking funnel, what action to drive, and which objections to defuse** — so content engages visitors, avoids bounces, and moves them toward booking.

It's the third guardrail layer in the writer system:

```
page template (what to build)  +  brand style guide (how to sound)  +  THIS (who + funnel + CTA + objections)
```

Voice always defers to the brand style guide; this layer governs audience targeting and conversion.

## What it covers (the three pillars you asked for)

1. **Detailed psychographic personas** — beyond demographics: travel **motivators** (status, relaxation, cultural education, wildlife-intimacy, romance, conservation), travel **stressors** (losing time, getting scammed, FOMO, decision-paralysis, safety, solo penalty), and **budget tier**.
2. **Funnel-stage mapping + exact CTAs** — every page declares its stage; the stage selects the persona, tone, and the verbatim CTA.
3. **Objection-handling library** — the real last-minute back-out reasons (safety, hidden fees, rigid cancellation, choosing wrong, crowds, solo penalty, accessibility, greenwashing, trust), each with a defuse strategy and writer-ready example copy.

## The "stage" question, answered

**Stage is declared per page, and overridable per section — not per project.** A single site spans the whole funnel (awareness wildlife/season guides → consideration "how to choose"/ship comparisons → decision availability/FAQ → closing enquiry). Each page declares `stage`, which then drives the matched persona + CTA + objections. A decision-stage enquiry band can be dropped into an awareness page via a section-level override.

## Files

| File | What it is |
|------|------------|
| **`audience-conversion-guardrail.template.yaml`** | **The deliverable.** Site-agnostic, fillable. 7 sections: personas, funnel stages, CTA system, objection library, trust/urgency, page-directive schema, global avoid. |
| **`examples/galapagosislands-travel.filled.yaml`** | Worked example for {{DOMAIN}} — personas, CTAs, objection copy, and per-page directives all tuned to that site (enquiry → {{BRAND}}; honest editorial voice). |

Research artifacts: `~/.scrape/.work/audience-conversion/` — `extracted/<site>.json` (CTA labels, objection/trust sentences, persona signals per site) and `synthesis.json` (the full consensus).

## How it was built (method)

Benchmarked the conversion best-practices of 10 converting sites in the segment:
`galapagosislands.com, galapatours, aquaexpeditions, metropolitan-touring, quasarex, ecoventura, celebritycruises, galapagos.org, expeditions (Lindblad), intrepidtravel`.

For each: captured CTA labels, objection/trust copy, persona-targeting signals, and funnel structure → distilled the consensus into personas, a funnel→CTA map, and an objection library.

### Key consensus findings (segment: Galápagos expedition cruise)
- **Lead-first, not instant-book.** Dominant CTAs are *Request a Quote / Check Availability / Talk to an Expert / Inquire* — instant "Book Now" is rarely the sole CTA for a $4–20k purchase.
- **A consistent persona set** recurs (wildlife lover, luxury, family, honeymoon, solo, diver, photographer, active senior, first-timer, eco/purpose) — and sites tag content to them explicitly.
- **Objections are pre-empted on-page** and repeat across sites (safety, choosing wrong, hidden fees, cancellation/flexibility, crowds, solo penalty, accessibility, greenwashing, trust).
- **Risk-reversal + human reassurance convert**: best-price guarantee, flexible/low deposit, doctor on board, certified guides, chat/call/specialist on every page.
- **Front-loaded social proof** (rating + review count, awards, years, named naturalists) defuses the trust objection.
- **Urgency is seasonal** (booking windows), never fake countdown timers.

## Use it for a new site

1. Copy `audience-conversion-guardrail.template.yaml` → `examples/<site>.filled.yaml`.
2. Fill the personas that matter for that site (draw from the consensus library).
3. Set the CTA system (primary lead CTA, secondary magnet, human fallback).
4. Tailor the objection library's `example_copy` to the brand voice.
5. Add a `page_directives.examples` block per real page (stage + persona + CTA + objections).
6. Inject the filled YAML into the writer alongside the brand style guide.

## Run a new conversion assessment (different segment)

Point the scraper at the new segment's top converting sites (homepage + a category page each), re-run the CTA/objection/persona extractor, and re-synthesize. The persona set and objection library will shift per niche; the structure holds.
