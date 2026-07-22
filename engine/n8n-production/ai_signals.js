// ─────────────────────────────────────────────────────────────────────────
// AI-WRITING SIGNAL DETECTOR  —  deterministic, code not LLM judgment.
//
// Runs inside Humanizing (WFP5). Two jobs, both in code:
//   clean(text)  — MECHANICAL fixes that are always safe: strip zero-width /
//                  invisible chars, normalize non-breaking spaces, collapse
//                  the exotic Unicode an LLM leaks. Never touches words.
//   detect(text) — measures every AI "footprint" (lexical / structural /
//                  statistical) and returns a pass/fail with quoted evidence.
//
// You cannot regex-delete "moreover" mid-sentence without breaking grammar, so
// the LLM does the REWRITING — but detection and the pass/fail GATE are here,
// in code, and a signal that survives fails the stage deterministically. The
// blocklists are DATA (see ai_signal_blocklist.json) so the monthly updater can
// grow them from the Wikipedia/arXiv sources without touching this logic.
//
// Sources baked in: the four-layer Master List (Lexical/Structural/Logical/
// Statistical), Wikipedia "Signs of AI writing", DetectGPT (burstiness /
// low-curvature), arXiv 2301.11305 & 2503.01659. See ai_signal_blocklist.json
// for provenance per term.
// ─────────────────────────────────────────────────────────────────────────

// Tunable thresholds — top of file, auditable.
const TH = {
  emDashPer1k: 4,        // AI overuses em-dashes; >4 per 1k words = tell
  burstinessMin: 0.45,   // coeff. of variation of sentence length; human prose is bursty
  trigramRepeatMax: 3,   // same non-trivial 3-gram appearing > this = mechanical repetition
  boldColonListMax: 2,   // "**Header:**" list items beyond this = AI list-with-bolded-headers tell
  notOnlyButAlsoMax: 1,  // "not only … but also" occurrences
  paraLenCVmin: 0.35,    // paragraph-length coefficient of variation (uniform = AI)
  listRatioMax: 0.5,     // fraction of body lines that are bullets/numbers
};

// Invisible / zero-width / exotic-space codepoints an LLM leaks. Stripped or
// normalized to a plain space. Curly quotes/dashes are NOT stripped here (they
// can be legitimate typography); em-dash DENSITY is measured instead.
const ZERO_WIDTH = /[​‌‍⁠﻿᠎­]/g;              // strip entirely
const NBSP_LIKE  = /[            　]/g; // -> space

// LLM copy-paste artifacts that must never reach a page (Wikipedia:Signs of AI
// writing — model markup-leak tokens from ChatGPT/Gemini/Grok/Perplexity).
const MARKUP_LEAK = /:contentReference\[[^\]]*\]|oaicite:\d+|oai_citation:?\d*|turn\d+search\d+|attributableIndex="[^"]*"|\[cite:\s*\d+\]|\[span_\d+\]|\[(?:start|end)_span\]|grok_render_citation_card_json|ppl-ai-file-upload|【[^】]*】/gi;

function clean(text) {
  let t = String(text || '');
  const before = t;
  t = t.replace(ZERO_WIDTH, '');
  t = t.replace(NBSP_LIKE, ' ');
  t = t.replace(MARKUP_LEAK, '');
  // collapse runs of spaces the normalization may create (but keep newlines)
  t = t.replace(/[ \t]{2,}/g, ' ');
  const stripped = (before.match(ZERO_WIDTH) || []).length;
  const nbsp = (before.match(NBSP_LIKE) || []).length;
  const leaks = (before.match(MARKUP_LEAK) || []).length;
  return { text: t, strippedInvisible: stripped, normalizedSpaces: nbsp, markupLeaks: leaks };
}

// ── loaded blocklists (data-driven; monthly updater grows these) ────────────
// Fallback baked-in lists so the detector works even if the JSON isn't wired.
const FALLBACK = {
  lexical: [
    'delve', 'tapestry', 'realm', 'landscape', 'cornerstone', 'pivotal', 'intricate',
    'robust', 'comprehensive', 'holistic', 'dynamic', 'transformative', 'paradigm',
    'multifaceted', 'nuance', 'nuanced', 'testament', 'boasts', 'boasting', 'elevate',
    'unleash', 'unlock', 'foster', 'garner', 'leverage', 'seamless', 'seamlessly',
    'bustling', 'vibrant', 'myriad', 'plethora', 'underscore', 'underscores', 'embark',
    'treasure trove', 'symphony', 'kaleidoscope', 'beacon', 'navigate', 'navigating',
    'showcase', 'showcasing', 'crucial', 'essential', 'vital', 'ever-evolving',
    'ever-changing', 'rich history', 'gem', 'hidden gem', 'stunning', 'breathtaking',
  ],
  phrases: [
    // transitions
    'moreover', 'furthermore', 'additionally', 'in essence', 'it is important to note',
    'it is worth mentioning', 'it is worth noting', 'as mentioned earlier',
    'at the end of the day', 'needless to say', 'that being said', 'when it comes to',
    // hedges
    'there is no one-size-fits-all', 'one-size-fits-all solution',
    'a complex and multifaceted issue', 'it is crucial to consider',
    'plays a crucial role', 'plays a significant role', 'plays a vital role',
    'plays a key role', 'it is important to remember',
    // conclusion signifiers
    'in conclusion', 'to summarize', 'in summary', 'all in all', 'ultimately,',
    // trigram tells
    'a testament to', 'the importance of', 'in the world of', 'the power of',
    'a wide range of', 'a variety of', 'when it comes to', 'in the realm of',
    'stands as a testament', 'a rich tapestry', 'navigating the complexities',
  ],
};

function loadLists(blocklist) {
  // Preferred: the calibrated tiered blocklist (ai_signal_blocklist.json).
  if (blocklist && Array.isArray(blocklist.tier_a_words)) {
    return {
      aWords: blocklist.tier_a_words || [],
      aPhrases: blocklist.tier_a_phrases || [],
      bWords: blocklist.tier_b_words || [],
      bPhrases: blocklist.tier_b_phrases || [],
    };
  }
  // Fallback: flat baked-in lists all treated as hard tells.
  return { aWords: FALLBACK.lexical, aPhrases: FALLBACK.phrases, bWords: [], bPhrases: [] };
}

// ── helpers ─────────────────────────────────────────────────────────────
function stripMarkup(t) {
  // strip HTML tags and internal markers so we measure PROSE, not scaffolding
  return String(t)
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\[(?:source|VERIFY|verify|human)[^\]]*\]/g, ' ')
    .replace(/&[a-z#0-9]+;/gi, ' ');
}
// prose with DATA TABLES removed — tables legitimately repeat facts and use
// dashes as separators, which are not AI tells. Statistical metrics run on this.
function proseNoTables(t) {
  const noTables = String(t)
    .replace(/<table[\s\S]*?<\/table>/gi, ' ')
    .replace(/(?:^|\n)\s*\|.*\|.*(?=\n|$)/g, ' ');   // markdown pipe rows
  return stripMarkup(noTables);
}
function sentences(prose) {
  return prose.split(/(?<=[.!?])\s+/).map(s => s.trim()).filter(s => s.split(/\s+/).length >= 3);
}
function words(s) { return s ? s.split(/\s+/).filter(Boolean).length : 0; }
function cv(arr) { // coefficient of variation
  if (arr.length < 2) return 1;
  const m = arr.reduce((a, b) => a + b, 0) / arr.length;
  if (!m) return 0;
  const v = arr.reduce((a, b) => a + (b - m) * (b - m), 0) / arr.length;
  return Math.sqrt(v) / m;
}

function detect(text, blocklist) {
  const lists = loadLists(blocklist);
  const raw = String(text || '');
  const prose = stripMarkup(raw);          // full prose (incl. table text) for lexical/phrase scan
  const proseNT = proseNoTables(raw);      // tables excluded for statistical metrics
  const low = prose.toLowerCase();
  const fails = [], notes = [];
  const wc = words(proseNT) || 1;

  // 1 · LEXICAL — TIER-A hard tells (near-zero in the human corpus) → FAIL;
  //     TIER-B context words humans use too → advisory NOTE only.
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const wordHits = (arr) => {
    const hits = [];
    for (const w of arr) {
      const n = (low.match(new RegExp(`\\b${esc(w)}\\b`, 'gi')) || []).length;
      if (n) hits.push(`${w}×${n}`);
    }
    return hits;
  };
  const phraseHits = (arr) => arr.filter(p => low.includes(p.toLowerCase())).map(p => `"${p}"`);

  const aLex = wordHits(lists.aWords), aPhr = phraseHits(lists.aPhrases);
  if (aLex.length) fails.push(`TIER-A lexical AI tells: ${aLex.slice(0, 25).join(', ')}`);
  if (aPhr.length) fails.push(`TIER-A phrase AI tells: ${aPhr.slice(0, 25).join(', ')}`);

  const bLex = wordHits(lists.bWords), bPhr = phraseHits(lists.bPhrases);
  const bDensity = ((bLex.length) / wc) * 1000;
  if (bLex.length || bPhr.length)
    notes.push(`TIER-B (voice-OK, watch density ${bDensity.toFixed(2)}/1k): ${[...bLex, ...bPhr].slice(0, 20).join(', ')}`);

  // 3 · STRUCTURAL
  const notOnly = (low.match(/not only\b[\s\S]{0,80}?\bbut also\b/g) || []).length;
  if (notOnly > TH.notOnlyButAlsoMax) fails.push(`"not only … but also" ×${notOnly} (max ${TH.notOnlyButAlsoMax})`);
  const boldColon = (raw.match(/(?:^|\n)\s*[-*]\s+\*\*[^*\n]+\*\*\s*:/g) || []).length
    + (raw.match(/<li>\s*<strong>[^<]+<\/strong>\s*:/gi) || []).length;
  if (boldColon > TH.boldColonListMax) fails.push(`bold-header-colon list items ×${boldColon} (AI list tell; max ${TH.boldColonListMax})`);

  // 4 · STATISTICAL — burstiness, em-dash density, trigram repetition, para uniformity
  // All measured on prose with tables EXCLUDED (tables legitimately repeat facts).
  const sents = sentences(proseNT);
  const lens = sents.map(words);
  const burst = cv(lens);
  if (sents.length >= 6 && burst < TH.burstinessMin)
    fails.push(`low burstiness ${burst.toFixed(2)} (uniform sentence length; human prose > ${TH.burstinessMin}) — vary long & short sentences`);

  const emDash = (proseNT.match(/—/g) || []).length;
  const emPer1k = (emDash / wc) * 1000;
  if (emPer1k > TH.emDashPer1k) fails.push(`em-dash overuse ${emPer1k.toFixed(1)}/1k words in prose (max ${TH.emDashPer1k})`);

  // Trigram repetition: only GENERIC grams (no digits, no all-proper-noun) count
  // as an AI tell. Repeated place names / prices / ship classes are facts, not
  // footprints — those are a NOTE. Curated n-gram tells live in the phrase list.
  const lowNT = proseNT.toLowerCase();
  const toks = lowNT.replace(/[^\p{L}0-9\s]/gu, ' ').split(/\s+/).filter(Boolean);
  const tri = {};
  for (let i = 0; i + 2 < toks.length; i++) {
    const g = toks[i] + ' ' + toks[i + 1] + ' ' + toks[i + 2];
    if (/\d/.test(g)) continue;                       // skip data (prices, counts)
    tri[g] = (tri[g] || 0) + 1;
  }
  // NOTE only: topical travel prose legitimately repeats place names / idioms
  // ("in the islands", "on a cruise") more than AI does — the human corpus
  // out-repeats the AI pages here, so this is not a discriminative hard gate.
  const STOP = /\b(the|a|an|of|to|in|on|for|and|or|is|are|it|as|at|by|with|that|this|your|you)\b/;
  const repeated = Object.entries(tri)
    .filter(([g, n]) => n > TH.trigramRepeatMax && g.length > 10 && STOP.test(g))
    .sort((a, b) => b[1] - a[1]).slice(0, 6);
  if (repeated.length) notes.push(`most-repeated phrases (advisory, vary if AI-like): ${repeated.map(([g, n]) => `"${g}"×${n}`).join(', ')}`);

  // paragraph-length uniformity
  const paras = raw.split(/\n{2,}|<\/p>/i).map(p => words(proseNoTables(p))).filter(n => n > 15);
  const paraCV = cv(paras);
  if (paras.length >= 4 && paraCV < TH.paraLenCVmin)
    notes.push(`paragraph lengths uniform (CV ${paraCV.toFixed(2)} < ${TH.paraLenCVmin}) — vary paragraph size`);

  notes.push(`burstiness ${burst.toFixed(2)}, em-dash/1k ${emPer1k.toFixed(1)}, sentences ${sents.length}, words ${wc}`);
  return { pass: fails.length === 0, fails, notes };
}

if (typeof module !== 'undefined' && module.exports) module.exports = { clean, detect, TH, FALLBACK };
