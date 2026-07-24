// ============================================================================
// Pattern Breaker — Phase 1 detector, JavaScript port for n8n Code node.
// Faithful, deterministic port of detector/detector.py. No LLM. No randomness.
// Thresholds are inlined (kept in sync with config/thresholds.json).
// Input:  items[0].json.text
// Output: one item with { text, flagged, metrics, flags, flagged_spans }
// ============================================================================

const CFG = {
  sentence_rhythm: { min_sentences: 4, cv_flag_below: 0.35, autocorr_lag1_flag_above: 0.55 },
  burstiness: { min_sentences: 4, sentence_burstiness_flag_below: 0.45, word_burstiness_flag_below: 0.30 },
  sentence_structure: { min_sentences: 4, opening_bigram_repeat_ratio_flag_above: 0.30, same_first_token_run_flag_at: 3 },
  paragraph_pattern: { min_paragraphs: 3, length_cv_flag_below: 0.25, parallel_opening_ratio_flag_above: 0.50 },
  ngram_formula: { ngram_sizes: [3, 4, 5], min_repeats_to_flag: 2, ignore_if_all_stopwords: true },
  transition_formula: {
    max_total_ratio_flag_above: 0.15, max_single_connective_count: 2,
    connectives: ["moreover","furthermore","additionally","in addition","in conclusion","overall","ultimately","notably","importantly","consequently","as a result","in summary","to summarize","in essence","essentially","it is worth noting","it's worth noting","it is important to note","when it comes to","in today's world","in the world of","nestled","whether you're","whether you are","look no further","rest assured"]
  },
  engine: { max_words: 5000, min_words_to_analyze: 40, verify_max_passes: 3 }
};

const STOPWORDS = new Set(["the","a","an","and","or","but","of","to","in","on","for","with","at","by","from","as","is","are","was","were","be","been","being","it","its","this","that","these","those","you","your","we","our","they","their","he","she","his","her","i","me","my"]);
const ABBREV = new Set(["mr","mrs","ms","dr","st","vs","etc","e.g","i.e","u.s","u.k"]);

const WORD_RE = /[A-Za-z0-9']+/g;
function words(s) { return (s.match(WORD_RE) || []); }

// --- sentence split with char offsets (mirror of Python _split_sentences) ---
function splitSentences(text) {
  const out = [];
  const re = /([.!?]+)(\s+|$)/g;
  let start = 0, m;
  const n = text.length;
  while ((m = re.exec(text)) !== null) {
    const end = m.index + m[1].length;
    const chunk = text.slice(start, end);
    const stripped = chunk.trim();
    if (stripped) {
      const tail = words(chunk.slice(-6).toLowerCase());
      const last = tail.length ? tail[tail.length - 1] : "";
      if (ABBREV.has(last) && end < n) { continue; }
      const realStart = start + (chunk.length - chunk.replace(/^\s+/, "").length);
      out.push({ text: text.slice(realStart, end).trim(), start: realStart, end });
    }
    start = re.lastIndex;
  }
  if (start < n && text.slice(start).trim()) {
    const rest = text.slice(start);
    const realStart = start + (rest.length - rest.replace(/^\s+/, "").length);
    out.push({ text: text.slice(realStart).trim(), start: realStart, end: n });
  }
  return out;
}

function parse(text) {
  // paragraph bounds
  const paraBounds = [];
  let pos = 0;
  for (const part of text.split(/\n\s*\n/)) {
    const s = text.indexOf(part, pos);
    const e = s + part.length;
    paraBounds.push([s, e]);
    pos = e;
  }
  const paraOf = (off) => {
    for (let i = 0; i < paraBounds.length; i++) if (paraBounds[i][0] <= off && off < paraBounds[i][1]) return i;
    return paraBounds.length - 1;
  };
  const sents = [];
  for (const s of splitSentences(text)) {
    const w = words(s.text.toLowerCase());
    if (!w.length) continue;
    const first = w[0];
    const bigram = w.length >= 2 ? w.slice(0, 2).join(" ") : first;
    sents.push({ text: s.text, start: s.start, end: s.end, para: paraOf(s.start),
      wc: w.length, first, bigram });
  }
  return sents;
}

// --- math helpers ---
const mean = xs => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
function variance(xs) { if (xs.length < 2) return 0; const m = mean(xs); return xs.reduce((a, x) => a + (x - m) ** 2, 0) / (xs.length - 1); }
const std = xs => Math.sqrt(variance(xs));
function cv(xs) { const m = mean(xs); return m === 0 ? 0 : std(xs) / m; }
function autocorr(xs) {
  const n = xs.length; if (n < 3) return 0;
  const m = mean(xs);
  const denom = xs.reduce((a, x) => a + (x - m) ** 2, 0);
  if (denom === 0) return 0;
  let num = 0; for (let i = 0; i < n - 1; i++) num += (xs[i] - m) * (xs[i + 1] - m);
  return num / denom;
}
function burstiness(xs) {
  const mu = mean(xs), sigma = std(xs);
  if (sigma + mu === 0) return 0;
  const b = (sigma - mu) / (sigma + mu);
  return Math.max(0, (b + 1) / 2);
}
const round = (x, d = 4) => Number(x.toFixed(d));

// --- detectors ---
function detectRhythm(sents, flags) {
  const c = CFG.sentence_rhythm;
  if (sents.length < c.min_sentences) return;
  const lengths = sents.map(s => s.wc);
  const _cv = cv(lengths), ac = autocorr(lengths);
  const span = [sents[0].start, sents[sents.length - 1].end];
  if (_cv < c.cv_flag_below)
    flags.push({ factor: "sentence_rhythm", scope: "document", reason: `Sentence-length CV ${round(_cv, 3)} below ${c.cv_flag_below} — sentences too uniform.`, metric: round(_cv), threshold: c.cv_flag_below, span_start: span[0], span_end: span[1], span_text: "[document]" });
  if (ac > c.autocorr_lag1_flag_above)
    flags.push({ factor: "sentence_rhythm", scope: "document", reason: `Sentence-length lag-1 autocorrelation ${round(ac, 3)} exceeds ${c.autocorr_lag1_flag_above} — repetitive rhythm.`, metric: round(ac), threshold: c.autocorr_lag1_flag_above, span_start: span[0], span_end: span[1], span_text: "[document]" });
}

function detectBurstiness(sents, text, flags) {
  const c = CFG.burstiness;
  if (sents.length < c.min_sentences) return;
  const sb = burstiness(sents.map(s => s.wc));
  const wb = burstiness(words(text).map(w => w.length));
  const span = [sents[0].start, sents[sents.length - 1].end];
  if (sb < c.sentence_burstiness_flag_below)
    flags.push({ factor: "burstiness", scope: "document", reason: `Sentence burstiness ${round(sb, 3)} below ${c.sentence_burstiness_flag_below} — lacks short/long variation.`, metric: round(sb), threshold: c.sentence_burstiness_flag_below, span_start: span[0], span_end: span[1], span_text: "[document]" });
  if (wb < c.word_burstiness_flag_below)
    flags.push({ factor: "burstiness", scope: "document", reason: `Word-length burstiness ${round(wb, 3)} below ${c.word_burstiness_flag_below} — word lengths too even.`, metric: round(wb), threshold: c.word_burstiness_flag_below, span_start: span[0], span_end: span[1], span_text: "[document]" });
}

function detectStructure(sents, flags) {
  const c = CFG.sentence_structure;
  if (sents.length < c.min_sentences) return;
  const counts = {};
  for (const s of sents) counts[s.bigram] = (counts[s.bigram] || 0) + 1;
  let best = null, freq = 0;
  for (const [k, v] of Object.entries(counts)) if (v > freq) { best = k; freq = v; }
  const ratio = freq / sents.length;
  if (ratio > c.opening_bigram_repeat_ratio_flag_above && freq >= 2) {
    for (const s of sents) if (s.bigram === best)
      flags.push({ factor: "sentence_structure", scope: "sentence", reason: `Sentence opening '${best}' repeats in ${freq}/${sents.length} sentences (ratio ${round(ratio, 2)} > ${c.opening_bigram_repeat_ratio_flag_above}).`, metric: round(ratio), threshold: c.opening_bigram_repeat_ratio_flag_above, span_start: s.start, span_end: s.end, span_text: s.text });
  }
  // runs of same first token
  let runStart = 0;
  for (let i = 1; i <= sents.length; i++) {
    const same = i < sents.length && sents[i].first === sents[runStart].first;
    if (!same) {
      const runLen = i - runStart;
      if (runLen >= c.same_first_token_run_flag_at)
        for (let j = runStart; j < i; j++)
          flags.push({ factor: "sentence_structure", scope: "sentence", reason: `${runLen} consecutive sentences start with '${sents[runStart].first}'.`, metric: runLen, threshold: c.same_first_token_run_flag_at, span_start: sents[j].start, span_end: sents[j].end, span_text: sents[j].text });
      runStart = i;
    }
  }
}

function detectParagraph(sents, text, flags) {
  const c = CFG.paragraph_pattern;
  const paras = {};
  for (const s of sents) (paras[s.para] = paras[s.para] || []).push(s);
  const ids = Object.keys(paras).map(Number).sort((a, b) => a - b);
  if (ids.length < c.min_paragraphs) return;
  const lengths = ids.map(p => paras[p].length);
  const _cv = cv(lengths);
  const openings = ids.map(p => paras[p][0].bigram);
  const oc = {};
  for (const o of openings) oc[o] = (oc[o] || 0) + 1;
  let parallel = 0;
  for (const v of Object.values(oc)) if (v >= 2) parallel += v;
  const pr = parallel / ids.length;
  if (_cv < c.length_cv_flag_below)
    for (const p of ids) { const b = paras[p];
      flags.push({ factor: "paragraph_pattern", scope: "paragraph", reason: `Paragraph lengths uniform (CV ${round(_cv, 3)} < ${c.length_cv_flag_below}) — mechanical paragraphing.`, metric: round(_cv), threshold: c.length_cv_flag_below, span_start: b[0].start, span_end: b[b.length - 1].end, span_text: text.slice(b[0].start, b[b.length - 1].end) }); }
  if (pr > c.parallel_opening_ratio_flag_above)
    for (const p of ids) { const b = paras[p]; if (oc[b[0].bigram] >= 2)
      flags.push({ factor: "paragraph_pattern", scope: "paragraph", reason: `Paragraph opening '${b[0].bigram}' reused across paragraphs (parallel ratio ${round(pr, 2)} > ${c.parallel_opening_ratio_flag_above}).`, metric: round(pr), threshold: c.parallel_opening_ratio_flag_above, span_start: b[0].start, span_end: b[b.length - 1].end, span_text: text.slice(b[0].start, b[b.length - 1].end) }); }
}

function detectNgram(text, flags) {
  const c = CFG.ngram_formula;
  const toks = [];
  let m;
  const re = /[A-Za-z0-9']+/g;
  while ((m = re.exec(text)) !== null) toks.push({ w: m[0].toLowerCase(), s: m.index, e: m.index + m[0].length });
  const N = toks.length;
  for (const size of c.ngram_sizes) {
    if (N < size) continue;
    const grams = {};
    for (let i = 0; i <= N - size; i++) {
      const slice = toks.slice(i, i + size);
      if (c.ignore_if_all_stopwords && slice.every(t => STOPWORDS.has(t.w))) continue;
      const key = slice.map(t => t.w).join(" ");
      (grams[key] = grams[key] || []).push(i);
    }
    for (const [g, idxs] of Object.entries(grams)) {
      if (idxs.length >= c.min_repeats_to_flag)
        for (const i of idxs)
          flags.push({ factor: "ngram_formula", scope: "span", reason: `${size}-word formula "${g}" repeats ${idxs.length} times.`, metric: idxs.length, threshold: c.min_repeats_to_flag, span_start: toks[i].s, span_end: toks[i + size - 1].e, span_text: text.slice(toks[i].s, toks[i + size - 1].e) });
    }
  }
}

function detectTransition(sents, flags) {
  const c = CFG.transition_formula;
  const conns = c.connectives.map(x => x.toLowerCase());
  const total = sents.length;
  if (!total) return;
  const perConn = {};
  const hits = [];
  for (const s of sents) {
    const low = s.text.toLowerCase().replace(/^\s+/, "");
    for (const conn of conns) {
      if (low.startsWith(conn)) { perConn[conn] = (perConn[conn] || 0) + 1; hits.push([conn, s]); break; }
    }
  }
  const tr = hits.length / total;
  if (tr > c.max_total_ratio_flag_above)
    for (const [conn, s] of hits)
      flags.push({ factor: "transition_formula", scope: "sentence", reason: `Formulaic connective opener '${conn}' — connectives open ${hits.length}/${total} sentences (ratio ${round(tr, 2)} > ${c.max_total_ratio_flag_above}).`, metric: round(tr), threshold: c.max_total_ratio_flag_above, span_start: s.start, span_end: s.end, span_text: s.text });
  for (const [conn, cnt] of Object.entries(perConn))
    if (cnt > c.max_single_connective_count)
      for (const [hc, s] of hits) if (hc === conn)
        flags.push({ factor: "transition_formula", scope: "sentence", reason: `Connective '${conn}' opens ${cnt} sentences (> ${c.max_single_connective_count}).`, metric: cnt, threshold: c.max_single_connective_count, span_start: s.start, span_end: s.end, span_text: s.text });
}

// --- dedup merged spans (mirror of Python _dedup_spans) ---
function dedupSpans(flags) {
  const concrete = flags.filter(f => ["sentence", "paragraph", "span"].includes(f.scope));
  const set = {};
  for (const f of concrete) set[`${f.span_start}:${f.span_end}`] = [f.span_start, f.span_end];
  const ranges = Object.values(set).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged = [];
  for (const [s, e] of ranges) {
    if (merged.length && s <= merged[merged.length - 1][1]) merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], e);
    else merged.push([s, e]);
  }
  return merged.map(([s, e]) => {
    const cover = concrete.filter(f => !(f.span_end <= s || f.span_start >= e));
    return { start: s, end: e, factors: [...new Set(cover.map(f => f.factor))].sort(), reasons: cover.map(f => f.reason) };
  });
}

// --- main ---
function detect(text) {
  const w = words(text);
  const sents = parse(text);
  const paras = new Set(sents.map(s => s.para)).size;
  const report = { text, flagged: false, word_count: w.length, sentence_count: sents.length, paragraph_count: paras, metrics: {}, flags: [], flagged_spans: [], notes: [] };
  if (w.length < CFG.engine.min_words_to_analyze) {
    report.notes.push(`Input ${w.length} words below min_words_to_analyze ${CFG.engine.min_words_to_analyze}; detection skipped.`);
    return report;
  }
  const flags = [];
  detectNgram(text, flags);
  detectRhythm(sents, flags);
  detectBurstiness(sents, text, flags);
  detectStructure(sents, flags);
  detectParagraph(sents, text, flags);
  detectTransition(sents, flags);

  const slen = sents.map(s => s.wc);
  const wlen = w.map(x => x.length);
  report.metrics = {
    sentence_length_cv: round(cv(slen)), sentence_length_autocorr_lag1: round(autocorr(slen)),
    sentence_burstiness: round(burstiness(slen)), word_burstiness: round(burstiness(wlen)),
    mean_sentence_length: round(mean(slen), 2)
  };
  report.flags = flags;
  report.flagged = flags.length > 0;
  report.flagged_spans = dedupSpans(flags);
  if (report.flagged && !report.flagged_spans.length)
    report.flagged_spans = sents.map(s => ({ start: s.start, end: s.end, factors: [...new Set(flags.map(f => f.factor))].sort(), reasons: flags.filter(f => f.scope === "document").map(f => f.reason) }));
  return report;
}

// n8n entry point
const input = $input.first().json;
const text = (input.body && input.body.text) || input.text || "";
return [{ json: detect(text) }];
