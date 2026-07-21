// ─────────────────────────────────────────────────────────────────────────
// DETERMINISTIC QA GATE — the publication contract, enforced in CODE not by an LLM.
//
// Runs at Auditor Review (WFP7) BEFORE the language model. Every check here is
// objective: it passes or fails on the bytes of the polished page, never on a
// model's opinion. A FAIL here routes the page to Needs Attention and the
// (expensive, fallible) LLM auditor is never called — so the model can neither
// override a hard failure nor waste credits on a page that is already broken.
// The LLM that runs after a PASS judges ONLY the irreducibly semantic things
// (truth-grounding against sources, Juan voice, fidelity) — never anything a
// regex can settle. See OUTPUT_HYGIENE.md, ENTITY_RULES.md, CTA_BLOCK.md.
//
// Single source of truth: this file is embedded verbatim into WFP7's "QA Gate
// (code)" node by add_deterministic_auditor_gate.py. Edit here, re-run the
// applier, commit. Never hand-edit the node in n8n.
//
// gate(html, rec) -> { pass: boolean, fails: string[], notes: string[] }
//   html = polished HTML string (the publication artifact)
//   rec  = Airtable record fields (Page Type, Suggested Word Count, Named Author,
//          Schema Markup Type). Missing fields degrade to the weakest safe check.
// ─────────────────────────────────────────────────────────────────────────

// Tunable thresholds — deliberately at the top so they are auditable/adjustable.
const TITLE_MIN = 50, TITLE_MAX = 60;
const DESC_MIN = 140, DESC_MAX = 160;
const WC_UNDER = 0.8;   // prose under 80% of target = thin  -> FAIL
const WC_OVER  = 1.6;   // prose over 160% of target = bloat -> FAIL (tables excluded)

// The fixed internal-marker vocabulary (OUTPUT_HYGIENE §Part H). None may survive
// to publication, INCLUDING inside JSON-LD.
const MARKERS = [
  '[source:', '[VERIFY]', '[verify]', '[human:', '[HT-',
  '[GC]', '[GCT]', '[CDF]', '[DPNG]', '[MASTER FACTS]', '[GT]'
];

// Guardrail sentences that have shipped as body copy (OUTPUT_HYGIENE §1). The
// positioning is practised, never announced. Substring match, case-insensitive.
const RECITALS = [
  'with no operator favoritism',
  'an honest trade-off, not a ranking',
  'luxury is the boat, not the map',
  "we don't play favorites",
  'we do not play favorites',
  'an independent editorial guide',
  'no operator favoritism',
];

// Entity hard-nos (ENTITY_RULES). The publisher is Galapagos Islands.Travel on
// galapagosislands.travel — never these.
const BANNED_ENTITY = ['Galapagos Travel Center', 'galapagosislands.com'];

const RETIRED_CTA = 'Talk to a Galápagos Specialist';

function decode(s) {
  return String(s).replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
}
// Visible text with a set of elements stripped. Used for prose word count.
function textStripping(html, tags) {
  let t = html;
  for (const tag of tags) t = t.replace(new RegExp(`<${tag}[\\s\\S]*?</${tag}>`, 'gi'), ' ');
  t = t.replace(/<[^>]+>/g, ' ');
  return decode(t).replace(/\s+/g, ' ').trim();
}
function words(s) { return s ? s.split(/\s+/).filter(Boolean).length : 0; }

function gate(html, rec) {
  rec = rec || {};
  const fails = [], notes = [];
  html = String(html || '');
  const H = html; // raw, markers/JSON-LD included

  // 1 · DOCUMENT STRUCTURE ------------------------------------------------
  if (!/<!doctype\s+html>/i.test(H)) fails.push('not a complete HTML document: missing <!DOCTYPE html>');
  for (const tag of ['html', 'head', 'body']) {
    if (!new RegExp(`<${tag}[\\s>]`, 'i').test(H)) fails.push(`missing <${tag}> element`);
  }

  // 2 · MARKER LEAKAGE (OUTPUT_HYGIENE Part H) ----------------------------
  for (const m of MARKERS) {
    if (H.includes(m)) {
      const i = H.indexOf(m);
      fails.push(`internal marker "${m}" leaked to publication: …${H.slice(Math.max(0, i - 25), i + 25).replace(/\s+/g, ' ')}…`);
    }
  }

  // 3 · GUARDRAIL RECITAL (OUTPUT_HYGIENE §1) -----------------------------
  const low = H.toLowerCase();
  for (const r of RECITALS) {
    if (low.includes(r)) fails.push(`guardrail recited as copy: "${r}" — the stance is practised, not announced`);
  }

  // 4 · ENTITY RULES ------------------------------------------------------
  for (const b of BANNED_ENTITY) {
    if (H.includes(b)) fails.push(`banned entity string present: "${b}"`);
  }

  // 5 · MARKDOWN / TILDE LEAKAGE (Part K) ---------------------------------
  if (/\*\*[^*\n]+\*\*/.test(H)) fails.push('markdown bold (**…**) survived into HTML');
  if (/(^|\n)\s*\|[^\n]*\|/.test(H)) fails.push('markdown pipe-table survived into HTML');
  // bare "~" meaning approximately (not part of a path/url/code)
  const tilde = H.match(/[\s(>]~(?=\s*[\$\d\w])/);
  if (tilde) {
    const i = H.indexOf(tilde[0]);
    fails.push(`bare "~" (approximately) ships to reader: …${H.slice(Math.max(0, i - 20), i + 25).replace(/\s+/g, ' ')}…`);
  }

  // 6 · META (title 50-60, description 140-160) — code counts, never the LLM
  const tm = H.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const dm = H.match(/<meta\s+name=["']description["']\s+content=["']([\s\S]*?)["']\s*\/?>/i);
  if (!tm) fails.push('no <title> element (an HTML comment is not a tag)');
  else { const t = decode(tm[1]).trim(); if (t.length < TITLE_MIN || t.length > TITLE_MAX) fails.push(`<title> is ${t.length} chars, gate is ${TITLE_MIN}-${TITLE_MAX}: "${t}"`); }
  if (!dm) fails.push('no <meta name="description"> element');
  else { const d = decode(dm[1]).trim(); if (d.length < DESC_MIN || d.length > DESC_MAX) fails.push(`meta description is ${d.length} chars, gate is ${DESC_MIN}-${DESC_MAX}`); }

  // 7 · CTA CLOSE (CTA_BLOCK / ENTITY_RULES) ------------------------------
  if (!/Voyagers Travel Company/i.test(H)) fails.push('CTA close missing operator: Voyagers Travel Company (travelers)');
  if (!/Latin Trails/i.test(H)) fails.push('CTA close missing operator: Latin Trails (trade/DMC)');
  if (H.includes(RETIRED_CTA)) fails.push(`retired CTA still present: "${RETIRED_CTA}"`);

  // 8 · JSON-LD: every block must parse; collect @types --------------------
  const ldTypes = new Set();
  let ldBlocks = 0, ldBad = 0;
  const re = /<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let m;
  while ((m = re.exec(H)) !== null) {
    ldBlocks++;
    let raw = decode(m[1]).trim();
    try {
      const obj = JSON.parse(raw);
      const walk = (o) => {
        if (Array.isArray(o)) return o.forEach(walk);
        if (o && typeof o === 'object') {
          if (o['@type']) [].concat(o['@type']).forEach(t => ldTypes.add(String(t)));
          Object.values(o).forEach(walk);
        }
      };
      walk(obj);
    } catch (e) { ldBad++; fails.push(`JSON-LD block ${ldBlocks} does not parse: ${e.message}`); }
  }
  if (ldBlocks === 0) fails.push('no JSON-LD structured data present');

  // 9 · SCHEMA TYPE RULES -------------------------------------------------
  const pageType = String(rec['Page Type'] || '');
  const isGuide = /Guide|Hub|Pillar|Island|FAQ|Final Answer|Blog/i.test(pageType) || pageType === '';
  if (isGuide && (ldTypes.has('Review') || ldTypes.has('AggregateRating')))
    fails.push(`schema mismatch: ${pageType || 'non-product'} page carries Review/AggregateRating JSON-LD`);
  // declared schema (record field) must actually appear
  const declared = String(rec['Schema Markup Type'] || '').split(/[+,/]/).map(s => s.trim()).filter(Boolean);
  if (declared.length) {
    for (const want of declared) {
      const key = want.replace(/\s+/g, '');
      const has = [...ldTypes].some(t => t.replace(/\s+/g, '').toLowerCase() === key.toLowerCase());
      if (!has) fails.push(`declared schema "${want}" (record) not found in page JSON-LD @types [${[...ldTypes].join(', ')}]`);
    }
  } else if (ldBlocks > 0 && ldBad === 0) {
    notes.push(`schema not declared on record; page ships @types [${[...ldTypes].join(', ')}]`);
  }

  // 10 · NAMED AUTHOR + AUTHOR SCHEMA (E-E-A-T) ---------------------------
  const hasAuthorLd = ldTypes.has('Person') || /"author"\s*:/i.test(H);
  if (!hasAuthorLd) fails.push('no author entity in JSON-LD (E-E-A-T authorship missing)');
  const namedAuthor = String(rec['Named Author'] || '').trim();
  if (namedAuthor && !H.includes(namedAuthor))
    fails.push(`record names author "${namedAuthor}" but it does not appear on the page`);
  if (!namedAuthor) notes.push('record has no Named Author; enforced author-schema presence only');

  // 11 · WORD COUNT — PROSE ONLY (tables/scripts/style excluded) ----------
  const suggested = Number(rec['Suggested Word Count'] || 0);
  if (suggested > 0) {
    const proseWc = words(textStripping(H, ['script', 'style', 'table']));
    const lo = Math.round(suggested * WC_UNDER), hi = Math.round(suggested * WC_OVER);
    if (proseWc < lo) fails.push(`prose word count ${proseWc} is thin: under ${lo} (${Math.round(WC_UNDER * 100)}% of target ${suggested})`);
    else if (proseWc > hi) fails.push(`prose word count ${proseWc} is bloated: over ${hi} (${Math.round(WC_OVER * 100)}% of target ${suggested}) — tables already excluded`);
    else notes.push(`prose word count ${proseWc} within [${lo}, ${hi}] of target ${suggested}`);
  }

  return { pass: fails.length === 0, fails, notes };
}

if (typeof module !== 'undefined' && module.exports) module.exports = { gate };
