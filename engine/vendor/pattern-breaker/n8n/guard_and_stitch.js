// ============================================================================
// Pattern Breaker — Phase 2 finalize (n8n Code node, run once for all items)
// Input: all span items, each with .original_span, .span_start/.end, and the
//        Claude HTTP response merged in (json.content[].text).
// Does: deterministic fact-guard (port of restructurer/factguard.py) per span,
//       applies light-blue highlight to major-change spans, stitches spans back
//       into the full document (HTML + plaintext-marker variants), and reports.
// If the upstream was a passthrough (nothing flagged), returns original unchanged.
// ============================================================================

const HL_OPEN_HTML = '<span class="pb-review" style="background-color:#cfe8ff">';
const HL_CLOSE_HTML = "</span>";
const HL_OPEN_MD = "[[PB-REVIEW]]";
const HL_CLOSE_MD = "[[/PB-REVIEW]]";

// ---- factguard port --------------------------------------------------------
const WORD = /[A-Za-z][A-Za-z'\-]*/g;
const NUMBER_CTX = /\b(\d[\d,\.]*)\s*([A-Za-z%$€£]+)?/g;
const NUM_WORDS = { zero:"0",one:"1",two:"2",three:"3",four:"4",five:"5",six:"6",seven:"7",eight:"8",nine:"9",ten:"10",eleven:"11",twelve:"12",thirteen:"13",fourteen:"14",fifteen:"15",sixteen:"16",seventeen:"17",eighteen:"18",nineteen:"19",twenty:"20",thirty:"30",forty:"40",fifty:"50",sixty:"60",seventy:"70",eighty:"80",ninety:"90",hundred:"100",thousand:"1000" };
const AMBIGUOUS = new Set(["one"]);
const COMMON = new Set(["The","A","An","This","That","These","Those","It","We","You","They","He","She","I","Our","Your","Their","His","Her","But","And","Or","So","Then","When","While","If","As","For","In","On","At","To","Of","With","From","By","Also","Here","There","Now","One","Two","Three","Bring","Get","Go","Come","Every","Each","Moreover","Furthermore","Additionally","Overall","Ultimately"]);

function numbers(text) {
  const out = new Set(); let m;
  NUMBER_CTX.lastIndex = 0;
  while ((m = NUMBER_CTX.exec(text)) !== null) out.add(m[1].replace(/,/g, ""));
  const ws = (text.toLowerCase().match(WORD) || []);
  for (const w of ws) if (NUM_WORDS[w] && !AMBIGUOUS.has(w)) out.add(NUM_WORDS[w]);
  return out;
}
function entities(text) {
  const ents = new Set();
  for (const sent of text.trim().split(/(?<=[.!?])\s+/)) {
    const toks = sent.match(WORD) || [];
    toks.forEach((w, i) => {
      if (!/[A-Z]/.test(w[0])) return;
      if (i === 0) return;
      if (COMMON.has(w)) return;
      if (w === w.toUpperCase() && w.length <= 3) return;
      ents.add(w);
    });
  }
  return ents;
}
const diff = (a, b) => [...a].filter(x => !b.has(x)).sort();
function guard(original, rewrite) {
  const on = numbers(original), rn = numbers(rewrite);
  const oe = entities(original), re_ = entities(rewrite);
  const newNums = diff(rn, on), newEnts = diff(re_, oe);
  const dropNums = diff(on, rn), dropEnts = diff(oe, re_);
  const hardFail = newNums.length || newEnts.length;
  const major = dropNums.length || dropEnts.length;
  const parts = [];
  if (newNums.length) parts.push(`introduced numbers ${JSON.stringify(newNums)}`);
  if (newEnts.length) parts.push(`introduced entities ${JSON.stringify(newEnts)}`);
  if (dropNums.length) parts.push(`dropped numbers ${JSON.stringify(dropNums)}`);
  if (dropEnts.length) parts.push(`dropped entities ${JSON.stringify(dropEnts)}`);
  return { ok: !hardFail, major_change: !!major,
    new_numbers: newNums, new_entities: newEnts,
    dropped_numbers: dropNums, dropped_entities: dropEnts,
    reason: parts.length ? parts.join("; ") : "clean" };
}
function extractText(json) {
  if (!json) return "";
  if (Array.isArray(json.content))
    return json.content.filter(b => b.type === "text").map(b => b.text).join("").trim();
  if (typeof json.text === "string") return json.text.trim();
  return "";
}

// ---- gather items ----------------------------------------------------------
// The HTTP node returns ONLY Claude's response body per item and drops the input
// fields, so we re-read each span's metadata from the "Prepare Spans" node by the
// SAME item index (n8n keeps item order 1:1 through the HTTP node). This makes the
// stitch robust regardless of the HTTP node's field-passing behaviour.
const httpItems = $input.all().map(i => i.json);
const prep = $("Prepare Spans").all().map(i => i.json);

// passthrough (nothing was flagged) — detected on the Prepare Spans output
const pass = prep.find(j => j.__passthrough);
if (pass) {
  const text = pass.original_text || "";
  return [{ json: {
    changed: false, needs_human_review: false, flags_cleared: true,
    output_text: text, output_html: text.replace(/\n/g, "<br>\n"),
    span_results: [], phase1: pass.phase1 || null,
    note: "No mechanical pattern detected; text returned unchanged."
  }}];
}

// pair each prepared span with its Claude response by index
const paired = prep
  .map((p, idx) => ({ p, http: httpItems[idx] }))
  .filter(x => x.p && x.p.span_start !== undefined)
  .sort((a, b) => a.p.span_start - b.p.span_start);
const originalText = (paired[0] && paired[0].p.original_text) || "";

const results = [];
for (const { p, http } of paired) {
  const s = p;
  const rewrite = extractText(http);           // Claude output for this span
  const original = s.original_span;
  let accepted = false, needsReview = false, majorChange = false, reason = "no output";
  let finalText = original;
  if (rewrite) {
    const g = guard(original, rewrite);
    reason = g.reason;
    if (g.ok) { accepted = true; finalText = rewrite; majorChange = g.major_change; needsReview = g.major_change; }
    else { accepted = false; finalText = original; needsReview = true; }  // hard fail -> keep original, flag
  } else { needsReview = true; }
  results.push({ start: s.span_start, end: s.span_end, factors: s.factors,
    original, rewrite, accepted, major_change: majorChange,
    needs_human_review: needsReview, guard_reason: reason });
}

// ---- stitch (walk original, replace accepted spans, highlight majors) -------
function stitch(highlight) {
  const open = highlight === "html" ? HL_OPEN_HTML : HL_OPEN_MD;
  const close = highlight === "html" ? HL_CLOSE_HTML : HL_CLOSE_MD;
  let out = "", cursor = 0;
  for (const r of results) {
    out += originalText.slice(cursor, r.start);
    let piece = r.accepted ? r.rewrite : r.original;
    if (r.needs_human_review) piece = open + piece + close;
    out += piece;
    cursor = r.end;
  }
  out += originalText.slice(cursor);
  return out;
}
const outputPlain = stitch("md");
const outputHtml = stitch("html").replace(/\n/g, "<br>\n");

const needsHuman = results.some(r => r.needs_human_review);
return [{ json: {
  changed: results.some(r => r.accepted),
  needs_human_review: needsHuman,
  output_text: outputPlain,
  output_html: outputHtml,
  span_results: results,
  summary: {
    spans_total: results.length,
    spans_accepted: results.filter(r => r.accepted).length,
    spans_flagged_for_review: results.filter(r => r.needs_human_review).length
  }
}}];
