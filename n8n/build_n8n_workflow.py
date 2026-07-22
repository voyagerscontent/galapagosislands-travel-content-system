"""
Build n8n workflow JSON files for the Voyagers Human Dictionary humanizer.

v1.4 — two workflows:

  1. n8n_workflow_code_node.json
     Deterministic-only pipeline (Webhook -> Code -> Respond).
     No LLM. Runs the full regex + Markov variant dictionary AND emits
     `flagged_spans` for context-trigger patterns the regex layer cannot
     cleanly rewrite.

  2. n8n_workflow_with_openai.json
     Two-pass pipeline with the OpenAI rewrite stage:
       Webhook
         -> Code (Humanize + emit flagged_spans)
         -> IF (any flags?)
              yes -> Split Out flagged_spans
                   -> HTTP Request (OpenAI Chat Completions)
                   -> Code (verbatim-guardrail validator + apply)
                   -> Aggregate back into a single item
                   -> Respond
              no  -> Respond
     The OpenAI node is called ONLY for flagged spans, uses
     temperature=0 + seed=42, and every LLM response is validated:
     the output MUST contain one of the pre-approved `human_variants`
     character-for-character; otherwise the flagged text is left as-is.

Auth: the HTTP Request node references credential `openAiApi` on the n8n
instance. Create an "OpenAI" credential in n8n (or paste the key into
the credential slot when importing).

Both files are importable directly via n8n's "Import from File".
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from humanizer import Humanizer  # noqa: E402

OUT_DIR = ROOT / "n8n"


def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# JS chunks reused across both workflows
# ---------------------------------------------------------------------------

def _humanize_js(rules: list[dict], triggers: list[dict]) -> str:
    """Emit the browser-portable humanize() JS + Markov picker + trigger scan.

    Placed inside an n8n Code node. Returns items shaped as:
        { text, original, word_count, truncated,
          replacement_count, replacements,
          flag_count, flagged_spans }
    """
    return f"""// ============================================================
// Voyagers Human Dictionary — deterministic AI-quirk humanizer v1.4
// Regex layer + Markov variant picker + context-trigger flagger.
// NO LLM in this node. Max 3000 words per item.
// ============================================================
const MAX_WORDS = 3000;
const MAX_CANDIDATES_PER_FLAG = 6;

const RULES = {json.dumps(rules, ensure_ascii=False)};
const TRIGGERS_RAW = {json.dumps(triggers, ensure_ascii=False)};

const COMPILED = RULES.map(r => ({{
  re: new RegExp(r.pattern, r.flags),
  key: r.key || '',
  variants: (r.variants && r.variants.length) ? r.variants : [r.replacement || ''],
  source: r.source,
}}));

// Compile trigger patterns. Python regex flags are inlined via (?i)/(?is)
// syntax so no JS-side flag mapping is needed — but JS regex does NOT
// support inline flag groups. Strip them and add the g + i flags in JS.
const TRIGGERS = TRIGGERS_RAW.map(t => {{
  let pat = t.pattern;
  let flags = 'g';
  const m = pat.match(/^\\(\\?([a-z]+)\\)/);
  if (m) {{
    if (m[1].includes('i')) flags += 'i';
    if (m[1].includes('s')) flags += 's';
    pat = pat.slice(m[0].length);
  }} else if (/\\(\\?i\\)/.test(pat)) {{
    flags += 'i';
    pat = pat.replace(/\\(\\?i\\)/g, '');
  }}
  return {{
    id: t.id,
    re: new RegExp(pat, flags),
    topic_bucket: t.topic_bucket,
    reason: t.reason,
    instruction_to_llm: t.instruction_to_llm,
    human_variants: t.human_variants || [],
  }};
}});

function fnv1a(s) {{
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {{
    h ^= s.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }}
  return h >>> 0;
}}
function stableHash() {{ return fnv1a(Array.from(arguments).join('\\u001f')); }}

function countWords(t) {{
  const m = (t || '').match(/\\S+/g);
  return m ? m.length : 0;
}}

function preserveCase(src, rep) {{
  if (!rep) return '';
  const trimmed = src.trim();
  const isUpper = trimmed.toUpperCase() === trimmed && /[A-Z]/.test(trimmed);
  if (isUpper) return rep.toUpperCase();
  const m = trimmed.match(/[a-zA-Z]/);
  if (m && m[0] === m[0].toUpperCase()) {{
    const idx = rep.search(/[a-zA-Z]/);
    if (idx >= 0) return rep.slice(0, idx) + rep[idx].toUpperCase() + rep.slice(idx + 1);
  }}
  return rep;
}}

function makePicker(seed) {{
  const state = new Map();
  return function pick(key, variants, context) {{
    const n = variants.length;
    if (n === 0) return {{ idx: 0, text: '' }};
    if (n === 1) return {{ idx: 0, text: variants[0] }};
    const st = state.get(key) || [-1, 0];
    const prev = st[0], occ = st[1];
    const h = stableHash(seed, key, String(prev), String(occ), context.slice(-64));
    const cand = [];
    for (let i = 0; i < n; i++) if (i !== prev) cand.push(i);
    const pool = cand.length ? cand : Array.from({{length:n}}, (_,i)=>i);
    const chosen = pool[h % pool.length];
    state.set(key, [chosen, occ + 1]);
    return {{ idx: chosen, text: variants[chosen] }};
  }};
}}

function flagContextTriggers(text, picker) {{
  const raw = [];
  for (const t of TRIGGERS) {{
    // reset lastIndex each scan
    t.re.lastIndex = 0;
    let m;
    while ((m = t.re.exec(text)) !== null) {{
      if (m[0].length === 0) {{ t.re.lastIndex++; continue; }}
      raw.push({{ start: m.index, end: m.index + m[0].length, trig: t, txt: m[0] }});
      if (!t.re.global) break;
    }}
  }}
  raw.sort((a,b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));
  const kept = [];
  let cursor = 0;
  for (const r of raw) {{
    if (r.start < cursor) continue;
    kept.push(r);
    cursor = r.end;
  }}
  const spans = [];
  for (const r of kept) {{
    const before = text.slice(Math.max(0, r.start - 80), r.start);
    const after = text.slice(r.end, Math.min(text.length, r.end + 80));
    const variants = r.trig.human_variants.map(v => (typeof v === 'string') ? v : (v.text || ''));
    const picked = picker(`trigger:${{r.trig.id}}`, variants, before + after);
    const ordered = [variants[picked.idx]].concat(variants.filter((_,i) => i !== picked.idx));
    spans.push({{
      trigger_id: r.trig.id,
      matched_text: r.txt,
      start: r.start,
      end: r.end,
      context_before: before,
      context_after: after,
      candidate_variants: ordered.slice(0, MAX_CANDIDATES_PER_FLAG),
      llm_instruction: r.trig.instruction_to_llm,
      topic_bucket: r.trig.topic_bucket,
      reason: r.trig.reason,
    }});
  }}
  return spans;
}}

function humanize(text, seedIn) {{
  if (typeof text !== 'string') text = '';
  const original = text;
  const wc = countWords(text);
  let truncated = false;
  if (wc > MAX_WORDS) {{
    const tokens = text.match(/\\S+|\\s+/g) || [];
    const kept = [];
    let n = 0;
    for (const t of tokens) {{
      if (/\\S/.test(t)) {{ if (n >= MAX_WORDS) break; n++; }}
      kept.push(t);
    }}
    text = kept.join('');
    truncated = true;
  }}
  const seed = seedIn || String(stableHash(text.slice(0, 256)));
  const pick = makePicker(seed);
  const replacements = [];
  let out = text;
  for (const c of COMPILED) {{
    out = out.replace(c.re, function () {{
      // String.replace callback signature is (match, p1, p2, ..., offset, string)
      // Groups may be zero-or-more. offset is always second-to-last, string is last.
      const args = arguments;
      const match = args[0];
      const whole = args[args.length - 1];
      const offset = args[args.length - 2];
      const start = Math.max(0, offset - 32);
      const end = Math.min(whole.length, offset + match.length + 32);
      const context = whole.slice(start, end);
      const picked = pick(c.key, c.variants, context);
      const cased = preserveCase(match, picked.text);
      replacements.push({{
        from: match, to: cased, source: c.source,
        variant_index: picked.idx, variant_count: c.variants.length,
      }});
      return cased;
    }});
  }}
  out = String(out).replace(/[ \\t]{{2,}}/g, ' ')
           .replace(/ +([,.!?;:])/g, '$1')
           .replace(/(^|\\n)[ \\t]*[,;][ \\t]*/g, '$1');

  const flagged = flagContextTriggers(out, pick);

  return {{
    text: out,
    original,
    word_count: Math.min(wc, MAX_WORDS),
    truncated,
    replacement_count: replacements.length,
    replacements,
    flag_count: flagged.length,
    flagged_spans: flagged,
  }};
}}

const results = [];
for (const item of $input.all()) {{
  const src = item.json.text ?? item.json.body?.text ?? item.json.input ?? '';
  const seed = item.json.seed ?? item.json.body?.seed ?? '';
  const r = humanize(String(src), String(seed || ''));
  // Preserve the original item metadata so downstream Split/Merge can
  // stitch spans back to the parent document.
  r.item_id = item.json.item_id || item.json.body?.item_id || null;
  results.push({{ json: r }});
}}
return results;
"""


_VALIDATOR_JS = """// ============================================================
// Verbatim guardrail validator — applies OpenAI rewrites only if
// the LLM output contains one of the pre-approved human_variants
// character-for-character. Otherwise the flagged text is kept as-is.
//
// This node receives ONE item per span from the OpenAI HTTP node.
// Each item's $json is the OpenAI chat completion response.
// Span metadata is pulled back from the Split Out node using n8n's
// paired-item alignment ($('Split Out spans').itemMatching(i).json).
//
// Output: { trigger_id, matched_text, start, end, replacement,
//           accepted: bool, reason, variant_used, llm_output }
// ============================================================
const results = [];
const items = $input.all();
for (let i = 0; i < items.length; i++) {
  const item = items[i];
  const oai = item.json || {};
  const llm = String(
    oai.choices?.[0]?.message?.content ??
    oai.openai_output ??
    ''
  ).trim();

  // Pull the corresponding span from Split Out (paired-item aligned).
  // Split Out hoists parent.flagged_spans fields to the top level, so span
  // fields (trigger_id, matched_text, start, end, candidate_variants, ...)
  // sit directly on the item's json.
  let span = {};
  try {
    const src = $('Split Out spans').itemMatching(i);
    span = (src && src.json) || {};
  } catch (e) {
    // Fallback: index-based lookup on the raw Split Out output.
    const all = $('Split Out spans').all();
    span = (all[i] && all[i].json) || {};
  }

  const cands = span.candidate_variants || [];
  let accepted = null;
  for (const c of cands) {
    if (llm && llm.includes(c)) { accepted = c; break; }
  }

  if (accepted) {
    results.push({ json: {
      trigger_id: span.trigger_id,
      matched_text: span.matched_text,
      start: span.start,
      end: span.end,
      replacement: llm,
      accepted: true,
      variant_used: accepted,
      llm_output: llm,
    }});
  } else {
    results.push({ json: {
      trigger_id: span.trigger_id,
      matched_text: span.matched_text,
      start: span.start,
      end: span.end,
      replacement: span.matched_text || '',
      accepted: false,
      reason: llm ? 'llm_output_missing_variant_verbatim' : 'llm_no_output',
      llm_output: llm,
    }});
  }
}
return results;
"""


_REASSEMBLE_JS = """// ============================================================
// Re-assemble the final humanized text after the LLM rewrite pass.
// Takes the parent document (item.json.parent_text + parent flagged_spans)
// plus the collected span-level replacements (from the Aggregate node)
// and applies replacements right-to-left so char offsets stay valid.
// ============================================================
const results = [];
for (const item of $input.all()) {
  const parent = item.json.parent || {};
  const spans = item.json.applied_spans || [];
  let text = parent.text || '';
  const sorted = [...spans].sort((a,b) => b.start - a.start);
  for (const s of sorted) {
    // Sanity: only replace if the current slice still matches the
    // originally flagged text — otherwise skip (offsets drifted).
    if (text.slice(s.start, s.end) === s.matched_text) {
      text = text.slice(0, s.start) + s.replacement + text.slice(s.end);
    }
  }
  results.push({ json: {
    text,
    original: parent.original,
    word_count: parent.word_count,
    truncated: parent.truncated,
    replacement_count: parent.replacement_count,
    replacements: parent.replacements,
    flag_count: parent.flag_count,
    flagged_spans: parent.flagged_spans,
    llm_rewrites: spans,
    accepted_rewrites: spans.filter(s => s.accepted).length,
    rejected_rewrites: spans.filter(s => !s.accepted).length,
  }});
}
return results;
"""


# ---------------------------------------------------------------------------
# Workflow 1: Deterministic-only (no LLM)
# ---------------------------------------------------------------------------

def build_code_node_workflow(rules: list[dict], triggers: list[dict]) -> dict:
    code = _humanize_js(rules, triggers)
    webhook_id = _uid()
    code_id = _uid()
    respond_id = _uid()
    return {
        "name": "Voyagers · Human Dictionary Humanizer (deterministic)",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "humanize",
                    "responseMode": "responseNode",
                    "options": {},
                },
                "id": webhook_id,
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "webhookId": webhook_id,
            },
            {
                "parameters": {"language": "javaScript", "jsCode": code},
                "id": code_id,
                "name": "Humanize (regex + flag)",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [520, 300],
            },
            {
                "parameters": {"respondWith": "json", "responseBody": "={{ $json }}"},
                "id": respond_id,
                "name": "Respond",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [840, 300],
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Humanize (regex + flag)", "type": "main", "index": 0}]]},
            "Humanize (regex + flag)": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
        },
        "active": False,
        "settings": {"executionOrder": "v1"},
        "versionId": _uid(),
        "meta": {"description": "v1.4 deterministic pipeline. Regex + Markov variants + context-trigger flagging. No LLM."},
        "id": _uid(),
        "tags": [],
    }


# ---------------------------------------------------------------------------
# Workflow 2: With OpenAI rewrite stage
# ---------------------------------------------------------------------------

def build_openai_workflow(rules: list[dict], triggers: list[dict]) -> dict:
    """
    Two-pass pipeline. Node layout:

      Webhook
        -> Code: Humanize (regex + flag)
        -> IF: flag_count > 0
             true  -> Set: carry parent
                   -> Split Out: flagged_spans (attach parent context)
                   -> HTTP Request: OpenAI chat completions
                   -> Code: verbatim guardrail
                   -> Aggregate spans
                   -> Merge with parent
                   -> Code: reassemble text
                   -> Respond
             false -> Respond
    """
    code = _humanize_js(rules, triggers)

    ids = {k: _uid() for k in (
        "webhook", "code_humanize", "if_flags", "set_carry", "split_spans",
        "http_openai", "code_validate", "aggregate", "merge_parent",
        "code_reassemble", "respond_ok", "respond_noflags",
    )}

    # Prompt for OpenAI — the assistant MUST return a full sentence containing
    # exactly one of the candidate_variants character-for-character.
    system_prompt = (
        "You are an editor helping a travel operator make marketing copy sound like a real "
        "traveler wrote it, not a language model. You will receive one AI-sounding sentence, "
        "some surrounding context, and a list of pre-approved rewrites collected from real "
        "traveler posts. Your job: pick ONE approved rewrite verbatim (character-for-character) "
        "and produce a short replacement sentence (1-2 sentences) that includes it and reads "
        "naturally in place of the AI sentence. Match tense and person to the surrounding "
        "text. Do not translate, paraphrase, or edit the chosen rewrite. Reply with ONLY the "
        "replacement text — no quotes, no explanation, no meta-commentary."
    )
    # This JS expression is evaluated inside the HTTP Request node's JSON body.
    # After Split Out (with fieldToSplitOut=parent.flagged_spans and
    # destinationFieldName=flagged_spans), each span's fields are hoisted to
    # the top level of $json.
    user_prompt_js = (
        "'CONTEXT BEFORE: ' + ($json.context_before || '') + \"\\n\" + "
        "'AI SENTENCE (replace this): ' + ($json.matched_text || '') + \"\\n\" + "
        "'CONTEXT AFTER: ' + ($json.context_after || '') + \"\\n\\n\" + "
        "'WHY IT NEEDS REWRITING: ' + ($json.reason || '') + \"\\n\" + "
        "'REWRITE STYLE: ' + ($json.llm_instruction || '') + \"\\n\\n\" + "
        "'APPROVED REWRITES (pick ONE and paste verbatim into your reply):\\n' + "
        "($json.candidate_variants || []).map(function(v,i){ return (i+1) + '. ' + v; }).join(\"\\n\")"
    )

    nodes = [
        # 0. Webhook
        {
            "parameters": {
                "httpMethod": "POST",
                "path": "humanize",
                "responseMode": "responseNode",
                "options": {},
            },
            "id": ids["webhook"],
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [100, 300],
            "webhookId": ids["webhook"],
        },
        # 1. Deterministic humanize + flag
        {
            "parameters": {"language": "javaScript", "jsCode": code},
            "id": ids["code_humanize"],
            "name": "Humanize (regex + flag)",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [340, 300],
        },
        # 2. IF flags > 0
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                    "conditions": [{
                        "id": _uid(),
                        "leftValue": "={{ $json.flag_count }}",
                        "rightValue": 0,
                        "operator": {"type": "number", "operation": "gt"},
                    }],
                    "combinator": "and",
                },
                "options": {},
            },
            "id": ids["if_flags"],
            "name": "IF flags > 0",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2,
            "position": [580, 300],
        },
        # 3. Set: carry parent object across the Split
        {
            "parameters": {
                "assignments": {
                    "assignments": [{
                        "id": _uid(),
                        "name": "parent",
                        "value": "={{ $json }}",
                        "type": "object",
                    }],
                },
                "options": {},
            },
            "id": ids["set_carry"],
            "name": "Carry parent",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": [820, 180],
        },
        # 4. Split Out flagged_spans - each item becomes one span (accessible as
        #    $json.flagged_spans.*) with parent still available via $('Carry parent').
        {
            "parameters": {
                "fieldToSplitOut": "parent.flagged_spans",
                "destinationFieldName": "flagged_spans",
                "include": "noOtherFields",
                "options": {},
            },
            "id": ids["split_spans"],
            "name": "Split Out spans",
            "type": "n8n-nodes-base.splitOut",
            "typeVersion": 1,
            "position": [1040, 180],
        },
        # 5. HTTP Request -> OpenAI
        {
            "parameters": {
                "method": "POST",
                "url": "https://api.openai.com/v1/chat/completions",
                "authentication": "predefinedCredentialType",
                "nodeCredentialType": "openAiApi",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "Content-Type", "value": "application/json"},
                    ],
                },
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    "={{ JSON.stringify({ "
                    "model: 'gpt-4o-mini', "
                    "temperature: 0, "
                    "seed: 42, "
                    "messages: [ "
                    "{ role: 'system', content: " + json.dumps(system_prompt) + " }, "
                    "{ role: 'user', content: (" + user_prompt_js + ") } "
                    "] }) }}"
                ),
                "options": {"response": {"response": {"responseFormat": "json"}}},
            },
            "id": ids["http_openai"],
            "name": "OpenAI · rewrite",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1260, 180],
        },
        # 6. Extract llm output + validate verbatim guardrail
        {
            "parameters": {
                "language": "javaScript",
                "jsCode": _VALIDATOR_JS,
            },
            "id": ids["code_validate"],
            "name": "Guardrail validate",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1480, 180],
        },
        # 7. Aggregate spans back to a single item — collect all input items
        #    into a single array field named `applied_spans`.
        {
            "parameters": {
                "aggregate": "aggregateAllItemData",
                "destinationFieldName": "applied_spans",
                "include": "allFields",
                "options": {},
            },
            "id": ids["aggregate"],
            "name": "Aggregate spans",
            "type": "n8n-nodes-base.aggregate",
            "typeVersion": 1,
            "position": [1700, 180],
        },
        # 8. Merge with parent (via a Set that pulls parent from Carry parent)
        {
            "parameters": {
                "assignments": {
                    "assignments": [
                        {"id": _uid(), "name": "parent",
                         "value": "={{ $('Carry parent').first().json.parent }}",
                         "type": "object"},
                        {"id": _uid(), "name": "applied_spans",
                         "value": "={{ $json.applied_spans }}",
                         "type": "array"},
                    ],
                },
                "options": {},
            },
            "id": ids["merge_parent"],
            "name": "Attach parent",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": [1920, 180],
        },
        # 9. Reassemble final text
        {
            "parameters": {"language": "javaScript", "jsCode": _REASSEMBLE_JS},
            "id": ids["code_reassemble"],
            "name": "Reassemble text",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [2140, 180],
        },
        # 10. Respond OK
        {
            "parameters": {"respondWith": "json", "responseBody": "={{ $json }}"},
            "id": ids["respond_ok"],
            "name": "Respond (with rewrites)",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1,
            "position": [2360, 180],
        },
        # 11. Respond (no flags path)
        {
            "parameters": {"respondWith": "json", "responseBody": "={{ $json }}"},
            "id": ids["respond_noflags"],
            "name": "Respond (no flags)",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1,
            "position": [820, 420],
        },
    ]

    connections = {
        "Webhook": {"main": [[{"node": "Humanize (regex + flag)", "type": "main", "index": 0}]]},
        "Humanize (regex + flag)": {"main": [[{"node": "IF flags > 0", "type": "main", "index": 0}]]},
        "IF flags > 0": {"main": [
            [{"node": "Carry parent", "type": "main", "index": 0}],       # true
            [{"node": "Respond (no flags)", "type": "main", "index": 0}], # false
        ]},
        "Carry parent": {"main": [[{"node": "Split Out spans", "type": "main", "index": 0}]]},
        "Split Out spans": {"main": [[{"node": "OpenAI · rewrite", "type": "main", "index": 0}]]},
        "OpenAI · rewrite": {"main": [[{"node": "Guardrail validate", "type": "main", "index": 0}]]},
        "Guardrail validate": {"main": [[{"node": "Aggregate spans", "type": "main", "index": 0}]]},
        "Aggregate spans": {"main": [[{"node": "Attach parent", "type": "main", "index": 0}]]},
        "Attach parent": {"main": [[{"node": "Reassemble text", "type": "main", "index": 0}]]},
        "Reassemble text": {"main": [[{"node": "Respond (with rewrites)", "type": "main", "index": 0}]]},
    }

    return {
        "name": "Voyagers · Human Dictionary Humanizer (with OpenAI rewrite)",
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "versionId": _uid(),
        "meta": {"description": "v1.4 two-pass pipeline. Regex + Markov + context triggers, with OpenAI rewrite gated by a verbatim guardrail. Requires an 'openAiApi' credential in n8n."},
        "id": _uid(),
        "tags": [],
    }


# ---------------------------------------------------------------------------
# Illustrative regex-chain workflow (kept for backwards compat)
# ---------------------------------------------------------------------------

def build_regex_chain_workflow(rules: list[dict], top_n: int = 40) -> dict:
    nodes = []
    connections = {}
    prev_name = "Manual Trigger"
    trigger_id = _uid()
    nodes.append({
        "parameters": {},
        "id": trigger_id,
        "name": prev_name,
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [200, 300],
    })
    x = 420
    for i, rule in enumerate(rules[:top_n]):
        name = f"Replace {i+1:02d}: {rule['pattern'][:32]}"
        node_id = _uid()
        nodes.append({
            "parameters": {
                "assignments": {
                    "assignments": [{
                        "id": _uid(),
                        "name": "text",
                        "value": (
                            "={{ ($json.text || '').replace("
                            f"new RegExp({json.dumps(rule['pattern'])}, {json.dumps(rule['flags'])}), "
                            f"{json.dumps(rule['replacement'])}) }}"
                        ),
                        "type": "string",
                    }],
                },
                "options": {},
            },
            "id": node_id,
            "name": name,
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": [x, 300],
        })
        connections[prev_name] = {"main": [[{"node": name, "type": "main", "index": 0}]]}
        prev_name = name
        x += 220
    return {
        "name": "Voyagers · Human Dictionary (Regex-Chain top-40, illustrative)",
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "versionId": _uid(),
        "meta": {"description": "Illustrative Set-node chain (top 40 rules). Use the Code-node workflow for the full ruleset."},
        "id": _uid(),
        "tags": [],
    }


# ---------------------------------------------------------------------------

def main() -> int:
    h = Humanizer()
    rules = h.dump_regex_rules()
    triggers = h.dump_triggers()

    wf1 = build_code_node_workflow(rules, triggers)
    (OUT_DIR / "n8n_workflow_code_node.json").write_text(
        json.dumps(wf1, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    wf2 = build_openai_workflow(rules, triggers)
    (OUT_DIR / "n8n_workflow_with_openai.json").write_text(
        json.dumps(wf2, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    wf3 = build_regex_chain_workflow(rules, top_n=40)
    (OUT_DIR / "n8n_workflow_regex_chain.json").write_text(
        json.dumps(wf3, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Wrote {len(rules)} regex rules and {len(triggers)} context triggers into:")
    print("  n8n/n8n_workflow_code_node.json     (deterministic only, no LLM)")
    print("  n8n/n8n_workflow_with_openai.json   (two-pass with OpenAI rewrite)")
    print("  n8n/n8n_workflow_regex_chain.json   (top-40 Set-node illustration)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
