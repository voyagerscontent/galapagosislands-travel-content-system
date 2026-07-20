# CTA BLOCK — the subtle dual close (hardcoded, every page)

Every page ends with this exact two-part close, quietly, at the very foot of the article — after
the content, after Related guides, as the last thing before the footer. It is subtle by design:
this is an editorial guide, and the close is a disclosure of who stands behind it, not a sales
band. One small block. No button-heavy band, no modal, no repetition elsewhere on the page.

## The exact copy (verbatim — do not paraphrase, reorder, or embellish)

> **Planning a Galápagos trip?** Travelers can contact **Voyagers Travel Company** for a full
> travel-planning service. Travel agents and tour operators looking for expert DMC services in the
> Galápagos can reach out to **Latin Trails**.

- **Travelers → Voyagers Travel Company** (the primary, consumer-facing path — full trip planning).
- **Trade (travel agents & tour operators) → Latin Trails** (the secondary aside — DMC services).

## Links (from SITE_CONFIG; webmaster confirms before publishing)
- Voyagers Travel Company → `{{CTA_TRAVELER_URL}}`
- Latin Trails → `{{CTA_TRADE_URL}}`

## Rules
1. **Verbatim.** The two sentences above appear exactly, once, at the foot of every page. Both
   company names must be present. This replaces the old single "Talk to a Galápagos Specialist"
   CTA — do not also emit that.
2. **Subtle.** Plain text or a quiet callout, not a loud CTA band. At most the traveler link
   carries the single accent; the Latin Trails line is a lighter aside. No hero modal, no sticky
   bar, no urgency, no "Book Now".
3. **This is the sanctioned operator disclosure.** Naming Voyagers (travelers) and Latin Trails
   (trade) is allowed here as the transparent relationship behind the guide — it is the ONE
   exception to the no-operator-favoritism rule, and only in this footer close. Elsewhere on the
   page, vessels and operators stay factual and comparative, never promoted.
4. It never contradicts the page. The guide stays honest ("whether or not you book with them").
