// ============================================================================
// Pattern Breaker — Phase 2 prep (n8n Code node, run once, output multiple items)
// Consumes the Phase-1 DetectionReport, and for EACH flagged span emits one item
// carrying the exact Anthropic payload (hardcoded system prompt + user template,
// deterministic Markov cadence seeds + paragraph shape). Non-flagged input yields
// zero span items but preserves the original text on a passthrough field.
// ============================================================================

// ---- HARDCODED system prompt (verbatim copy of restructurer/restructure.py) --
const SYSTEM_PROMPT = `You are a constrained text-restructuring tool, NOT a writer with creative freedom.

You will receive ONE short flagged text span at a time, plus the exact mechanical
pattern(s) a deterministic detector found in it. Your ONLY job is to break those
patterns while preserving 100% of the meaning.

NON-DEVIATION RULES (violating any is a failure):
1. DO NOT add any fact, name, place, number, date, price, or claim that is not
   already present in the span. Zero new information.
2. DO NOT remove any fact, name, place, number, date, or price that IS present.
   Preserve every entity and every quantity exactly (you may spell a number in
   words, e.g. "3" -> "three", but never change its value).
3. DO NOT add filler, fluff, marketing adjectives, or padding to hit a length.
4. Preserve the original language and tense. If the span is Spanish, answer in
   Spanish. If English, English.

WHAT YOU MUST DO (this is why you exist):
- Break the detected pattern. If sentences were uniform in length, make them
  deliberately UNEVEN. This is mandatory: include at least one VERY SHORT
  sentence (2-5 words) AND at least one LONG sentence (18+ words) in your
  rewrite, so the length variation (burstiness) is high. Do NOT make every
  sentence a similar length. A one- or two-word sentence fragment is allowed if
  it preserves meaning.
- If sentence openings repeated, start each sentence differently.
- If paragraph structure was uniform, VARY it: use the suggested paragraph shape
  (number of paragraphs and sentences each) as a target, without adding content.
- If formulaic connectives (Moreover, Furthermore, Additionally, In conclusion)
  were used, remove or replace them with natural phrasing.
- You are given MARKOV CADENCE SEEDS drawn from the text's own words and a human
  travel corpus. Use them ONLY as inspiration for rhythm and natural connective
  variety. They are NOT facts to insert. Never state anything from a seed as a
  claim about the subject.

OUTPUT FORMAT:
Return ONLY the rewritten span as plain text. No preamble, no explanation, no
quotes around it, no markdown fences.`;

const USER_TEMPLATE = (span, reasons, shape, seeds) =>
`FLAGGED SPAN (rewrite this, break the pattern, keep every fact):
---
${span}
---

DETECTED PATTERNS TO BREAK:
${reasons}

TARGET PARAGRAPH SHAPE (approximate, do NOT pad to reach it):
${shape}

MARKOV CADENCE SEEDS (rhythm/connective inspiration only — NOT facts):
${seeds}

Rewrite the span now. Output only the rewritten text.`;

const MODEL = $vars && $vars.PB_CLAUDE_MODEL ? $vars.PB_CLAUDE_MODEL : "claude-sonnet-4-6";
const TEMPERATURE = 0.4;

// ---- deterministic seeded PRNG (sha256 -> mulberry32) ----------------------
const crypto = require("crypto");
function seedFrom(text, salt) {
  const h = crypto.createHash("sha256").update((salt || "") + "::" + text).digest("hex");
  return parseInt(h.slice(0, 8), 16) >>> 0;
}
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const WORD_RE = /[A-Za-z0-9']+/g;

// ---- compact Markov (span + optional corpus subset) ------------------------
function buildChain(text, corpusPhrases) {
  const order = 2;
  const chain = {};
  const starts = [];
  const train = (t) => {
    for (const sent of t.trim().split(/(?<=[.!?])\s+/)) {
      const toks = sent.match(WORD_RE) || [];
      if (toks.length < order + 1) continue;
      starts.push(toks.slice(0, order));
      for (let i = 0; i < toks.length - order; i++) {
        const key = toks.slice(i, i + order).join(" ");
        (chain[key] = chain[key] || []).push(toks[i + order]);
      }
    }
  };
  train(text); train(text); // weight span twice
  if (corpusPhrases) for (const p of corpusPhrases) train(p);
  return { chain, starts, order };
}
function cadenceSeeds(spanText, mk, n = 5, minLen = 2, maxLen = 6) {
  if (!mk.starts.length) return [];
  const rnd = mulberry32(seedFrom(spanText, ""));
  const ri = (lo, hi) => lo + Math.floor(rnd() * (hi - lo + 1));
  const out = [], seen = new Set();
  let attempts = 0;
  while (out.length < n && attempts < n * 8) {
    attempts++;
    const target = ri(minLen, maxLen);
    const key = mk.starts[Math.floor(rnd() * mk.starts.length)];
    const words = key.slice();
    let cur = key.join(" ");
    while (words.length < target) {
      const ch = mk.chain[cur];
      if (!ch || !ch.length) break;
      const nxt = ch[Math.floor(rnd() * ch.length)];
      words.push(nxt);
      cur = words.slice(-mk.order).join(" ");
    }
    const frag = words.join(" ").trim(), low = frag.toLowerCase();
    if (words.length >= minLen && frag && !seen.has(low)) { seen.add(low); out.push(frag); }
  }
  return out;
}
function paragraphShape(spanText) {
  const rnd = mulberry32(seedFrom(spanText, "shape:"));
  const ri = (lo, hi) => lo + Math.floor(rnd() * (hi - lo + 1));
  const nPara = ri(1, 3);
  const shape = [];
  for (let i = 0; i < nPara; i++) shape.push(ri(1, 5));
  return { paragraphs: nPara, sentences_per_paragraph: shape };
}

// ---- main ------------------------------------------------------------------
const report = $input.first().json;
const fullText = report.text || "";

// NOTE ON MARKOV SOURCE (intentional difference from the Python reference):
// The Python engine also trains on dictionary/human_corpus.json (2,307 human
// travel sentences). Inlining 100KB+ into a Code node is impractical, and the
// cadence seeds are "rhythm inspiration only" — never facts (the deterministic
// fact-guard downstream rejects any new number/entity regardless of seed source).
// So the native node trains the Markov on the SPAN'S OWN TEXT only. Seeds stay
// deterministic (seeded PRNG) and on-topic; safety is unchanged.
const corpus = null;

if (!report.flagged || !report.flagged_spans || !report.flagged_spans.length) {
  return [{ json: { __passthrough: true, original_text: fullText, flagged: false,
    phase1: report } }];
}

const items = [];
report.flagged_spans.forEach((sp, idx) => {
  const spanText = fullText.slice(sp.start, sp.end);
  const mk = buildChain(spanText, corpus);
  const seeds = cadenceSeeds(spanText, mk);
  const shape = paragraphShape(spanText);
  const reasons = (sp.reasons && sp.reasons.length ? sp.reasons : ["Mechanical pattern detected."])
    .map(r => "- " + r).join("\n");
  const shapeStr = `${shape.paragraphs} paragraph(s); sentences each: [${shape.sentences_per_paragraph.join(", ")}]`;
  const seedStr = seeds.length ? seeds.map(s => "• " + s).join("\n") : "(none available)";
  const userMsg = USER_TEMPLATE(spanText, reasons, shapeStr, seedStr);

  items.push({ json: {
    __passthrough: false,
    span_index: idx,
    span_start: sp.start,
    span_end: sp.end,
    factors: sp.factors || [],
    original_span: spanText,
    original_text: fullText,
    anthropicPayload: {
      model: MODEL,
      max_tokens: 1024,
      temperature: TEMPERATURE,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: userMsg }]
    }
  }});
});
return items;
