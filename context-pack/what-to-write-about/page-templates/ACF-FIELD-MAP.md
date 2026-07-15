# ACF Field Map — Expedition Cruise Hub (Galápagos base)

How `galapagos.html` (the filled ideal build) maps to **Advanced Custom Fields** in WordPress.

## The two-layer model

This template separates content into two layers — only the second becomes editable fields:

| Layer | What it is | In WordPress |
|-------|------------|--------------|
| **Authored layer** | Destination + ranking knowledge: hero framing, intro/why copy, how-to-choose guide, best-time answer, FAQ Q&A, conservation framing, checklist, section headings. **Hard-coded in the template.** | Lives in the page template (PHP/block markup), *not* in ACF. Edit it by editing the template, not the post. |
| **ACF layer** | Business / inventory / proof data that changes per page or per brand. The `{{TOKENS}}` in `galapagos.html`. | ACF fields on the page (or theme options for brand-wide values). |

> **Why split this way:** the authored layer *is* the product — it encodes the design/UX/SEO/AIO factors we want identical on every build. Exposing it as free-text ACF would let editors dilute it. Keep it in the template; expose only the variables.

**Token → field-name convention:** lowercase the token. `{{BRAND_NAME}}` → `brand_name`, `{{ITIN_1_PRICE}}` → repeater `itineraries` › row › sub-field `price`.

---

## Field group 1 — `brand_global` (Theme Options, set once)

Brand-wide values reused across every destination page. Put these in an ACF **Options Page** so they're not re-entered per post.

| ACF field | Type | Token | Notes |
|-----------|------|-------|-------|
| `brand_name` | Text | `{{BRAND}}` | {{BRAND}} |
| `site_url` | URL | `{{SITE_URL}}` | Homepage, used in breadcrumb + Org schema |
| `logo_url` | Image (return URL) | `{{LOGO_URL}}` | Org schema logo |
| `phone` | Text | `{{PHONE}}` | reservations contactPoint |
| `facebook_url` | URL | `{{FACEBOOK_URL}}` | Org `sameAs` |
| `instagram_url` | URL | `{{INSTAGRAM_URL}}` | Org `sameAs` |
| `footer_positioning` | Text | `{{FOOTER_POSITIONING}}` | One-line footer tagline |
| `year` | (auto) | `{{YEAR}}` | Render `date('Y')` — do not make editable |

---

## Field group 2 — `hub_page` (per page)

Attach to the "Cruise Hub" page template / CPT.

### 2a. Hero + meta
| ACF field | Type | Token |
|-----------|------|-------|
| `canonical_url` | URL | `{{CANONICAL_URL}}` |
| `hero_image` | Image | `{{HERO_IMAGE_URL}}` / `{{HERO_ALT}}` (use the image's alt text) |
| `price_from` | Number | `{{PRICE_FROM}}` |
| `duration_range` | Text | `{{DURATION_RANGE}}` e.g. "4–8" |
| `ship_count` | Number | `{{SHIP_COUNT}}` |

### 2b. Trust strip
| ACF field | Type | Token |
|-----------|------|-------|
| `years_operating` | Number | `{{YEARS}}` |
| `travellers_hosted` | Text | `{{TRAVELLERS}}` e.g. "100,000+" |

### 2c. Section images (alt text)
| ACF field | Type | Token |
|-----------|------|-------|
| `expect_image` | Image | `{{EXPECT_IMG_ALT}}` |
| `besttime_image` | Image | `{{BESTTIME_IMG_ALT}}` |

### 2d. Ships intro copy (tab panels)
| ACF field | Type | Token |
|-----------|------|-------|
| `ships_cabins_copy` | Textarea | `{{SHIPS_CABINS_COPY}}` |
| `ships_excursions_copy` | Textarea | `{{SHIPS_EXCURSIONS_COPY}}` |
| `ships_cuisine_copy` | Textarea | `{{SHIPS_CUISINE_COPY}}` |

### 2e. Video (optional)
| ACF field | Type | Token |
|-----------|------|-------|
| `video_url` | URL | `{{VIDEO_URL}}` |
| `video_title` | Text | `{{VIDEO_TITLE}}` |
| `video_desc` | Textarea | `{{VIDEO_DESC}}` |
| `video_poster` | Image | `{{VIDEO_POSTER_URL}}` |
| `video_upload_date` | Date Picker | `{{VIDEO_UPLOAD_DATE}}` |

---

## Field group 3 — Repeaters (per page)

### `itineraries` (Repeater · §9 + ItemList schema) — **core conversion unit**
Min 3 rows. Each row also feeds one `ItemList` JSON-LD entry.

| Sub-field | Type | Token (row 1) | Rule |
|-----------|------|---------------|------|
| `image` | Image | `{{ITIN_1_IMG_ALT}}` | uniform card crop |
| `name` | Text | `{{ITIN_1_NAME}}` | **must be unique** per row (anti-pattern: duplicate headings) |
| `days` | Number | `{{ITIN_1_DAYS}}` | |
| `route` | Text | `{{ITIN_1_ROUTE}}` | e.g. "West & Central" |
| `rating` | Number | `{{ITIN_1_RATING}}` | |
| `short` | Text | `{{ITIN_1_SHORT}}` | 1–2 line blurb → schema `description` |
| `price` | Number | `{{ITIN_1_PRICE}}` | → Offer `price` (USD) |
| `url` | URL | `{{ITIN_1_URL}}` | → Offer `url` + "View Itinerary" |

### `ships` (Repeater · §10)
| Sub-field | Type | Token (row 1) |
|-----------|------|---------------|
| `image` | Image | `{{SHIP_1_IMG_ALT}}` |
| `name` | Text | `{{SHIP_1_NAME}}` |
| `spec` | Text | `{{SHIP_1_SPEC}}` (class · guests · cabins) |
| `url` | URL | `{{SHIP_1_URL}}` |

### `guides` (Repeater · §11)
| Sub-field | Type | Token (row 1) |
|-----------|------|---------------|
| `photo` | Image | `{{GUIDE_1_IMG_ALT}}` |
| `name` | Text | `{{GUIDE_1_NAME}}` |
| `cred` | Text | `{{GUIDE_1_CRED}}` (credential · years · specialty) |

### `reviews` (Repeater · §14 + Review schema) — ⚠️ honesty/policy gate
**Use only genuine, verifiable reviews.** Each row feeds one `Review` JSON-LD entry; the page-level `rating` + `review_count` feed `AggregateRating`. Fabricated rating schema risks a Google manual action.

| Sub-field | Type | Token (row 1) |
|-----------|------|---------------|
| `text` | Textarea | `{{REVIEW_1_TEXT}}` |
| `author` | Text | `{{REVIEW_1_AUTHOR}}` |
| `meta` | Text | `{{REVIEW_1_META}}` (country · date) |

Page-level (group 2): `rating` (Number) → `{{RATING}}`, `review_count` (Number) → `{{REVIEW_COUNT}}`.

### `impact_stats` (Repeater · §12)
| Sub-field | Type | Token (row 1) |
|-----------|------|---------------|
| `number` | Text | `{{IMPACT_1_NUM}}` |
| `label` | Text | `{{IMPACT_1_LABEL}}` |

> **`included_items`, `audience_cards`** (§5, §6) are currently hard-coded in `galapagos.html`. They're stable for Galápagos; promote to repeaters only if editors need to change them per page.

---

## Per-destination investigation hooks 🔬

When we re-run the teardown method for **Amazon / Patagonia / Antarctica**, these are the parts that change. They are **hard-coded** in `galapagos.html` and must be re-authored per destination (not ACF — they're knowledge, not inventory):

| Hook | Galápagos value (this build) | What the next investigation must determine |
|------|------------------------------|--------------------------------------------|
| Destination name + breadcrumb | "Galápagos" | Destination label, H1, breadcrumb |
| Hero subhead promise | "world's greatest wildlife voyage…" | The one-line emotional hook per destination |
| Season framing (§8) | warm Dec–May / cool garúa Jun–Nov + species calendar | Each destination's seasons, wildlife events, weather |
| Region choice (§7) | east vs west islands | The destination's route/region decision axis |
| Permits & fees (§7, §15) | $200 park fee + $20 INGALA card | Destination's entry fees / permits (e.g. IAATO for Antarctica) |
| Guide certification (§11) | "National Park-Certified" | Destination's guide-credential standard |
| FAQ set (§16) | 8 Galápagos PAA questions + answers | Re-pull People-Also-Ask per destination; keep 8–12, answer-first |
| What's included (§5) | flights/excursions/guides/meals/gear | Destination-specific inclusions |
| Conservation framing (§12) | marine debris, invasive species | Destination's conservation story |

**Method to re-run per destination:** same as the Galápagos study — scrape top-10 SERP for "`<destination>` cruises" → per-page teardown → design + UX synthesis → fill these hooks. Output trail lives under `../.scrape/.work/google-search/`.

---

## Build checklist (WordPress)

- [ ] Create ACF Options Page → field group 1 (`brand_global`).
- [ ] Create "Cruise Hub" page template (or CPT) → field groups 2 + 3.
- [ ] Port `galapagos.html` markup into the template; replace each `{{TOKEN}}` with its ACF call (`the_field()` / `get_field()`), loop repeaters with `have_rows()`.
- [ ] Generate the 6 JSON-LD blocks server-side from the same fields (single source of truth — never let the visible FAQ and FAQPage schema drift).
- [ ] Keep `<body class="is-production">` (hides any editor notes).
- [ ] Drop real images into the media library; enforce <60 images, lazy-load below the fold.
- [ ] **Reviews + AggregateRating must be genuine** before going live.
- [ ] Validate every schema block in the [Rich Results Test](https://search.google.com/test/rich-results).
- [ ] Run the anti-pattern checklist at the end of `TEMPLATE-SPEC.md`.
