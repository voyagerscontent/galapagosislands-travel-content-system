"""
Build an n8n workflow JSON that maps AI-generated words/phrases to human ones
using a hardcoded Code node (no LLM). Two variants are produced:

  1. n8n_workflow_code_node.json   -> single Code node with ordered rules
                                      (recommended — one file, no branching)
  2. n8n_workflow_regex_chain.json -> a chain of "Edit Fields (Set)" nodes,
                                      one per top-N rules (illustrative only —
                                      full 1000+ rule chain would be huge)

Both are importable directly into n8n via "Import from File".
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


def build_code_node_workflow(rules: list[dict]) -> dict:
    """
    A minimal 3-node workflow: Webhook -> Code -> Respond.
    The Code node embeds the full ordered ruleset and runs deterministic regex
    replacements. No LLM. No network. No dependency on external packages.
    """
    code = f"""// ============================================================
// Voyagers Human Dictionary — deterministic AI-quirk humanizer v1.1
// Hardcoded ruleset compiled from the JSON dictionaries.
// NO LLM. Pure regex + Markov variant picker. Max 3000 words per item.
// ============================================================
const MAX_WORDS = 3000;

const RULES = {json.dumps(rules, ensure_ascii=False)};

const COMPILED = RULES.map(r => ({{
  re: new RegExp(r.pattern, r.flags),
  key: r.key || '',
  variants: (r.variants && r.variants.length) ? r.variants : [r.replacement || ''],
  source: r.source,
}}));

function fnv1a(s) {{
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {{
    h ^= s.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }}
  return h >>> 0;
}}
function stableHash() {{ return fnv1a(Array.from(arguments).join('\u001f')); }}

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
      if (/\\S/.test(t)) {{
        if (n >= MAX_WORDS) break;
        n++;
      }}
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
    out = out.replace(c.re, (match, _p1, offset, whole) => {{
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
  out = out.replace(/[ \\t]{{2,}}/g, ' ')
           .replace(/ +([,.!?;:])/g, '$1')
           .replace(/(^|\\n)[ \\t]*[,;][ \\t]*/g, '$1');
  return {{
    text: out,
    original,
    word_count: Math.min(wc, MAX_WORDS),
    truncated,
    replacement_count: replacements.length,
    replacements,
  }};
}}

// n8n Code node — process every incoming item
const results = [];
for (const item of $input.all()) {{
  const src = item.json.text ?? item.json.body?.text ?? item.json.input ?? '';
  const seed = item.json.seed ?? item.json.body?.seed ?? '';
  const r = humanize(String(src), String(seed || ''));
  results.push({{ json: r }});
}}
return results;
"""
    webhook_id = _uid()
    code_id = _uid()
    respond_id = _uid()

    workflow = {
        "name": "Voyagers · Human Dictionary Humanizer",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "humanize",
                    "responseMode": "responseNode",
                    "options": {}
                },
                "id": webhook_id,
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [200, 300],
                "webhookId": webhook_id,
            },
            {
                "parameters": {
                    "language": "javaScript",
                    "jsCode": code
                },
                "id": code_id,
                "name": "Humanize (hardcoded rules)",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [520, 300],
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ $json }}"
                },
                "id": respond_id,
                "name": "Respond",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [840, 300],
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Humanize (hardcoded rules)", "type": "main", "index": 0}]]},
            "Humanize (hardcoded rules)": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
        },
        "active": False,
        "settings": {"executionOrder": "v1"},
        "versionId": _uid(),
        "meta": {"description": "Deterministic AI-quirk humanizer. Hardcoded travel dictionary. No LLM."},
        "id": _uid(),
        "tags": [],
    }
    return workflow


def build_regex_chain_workflow(rules: list[dict], top_n: int = 40) -> dict:
    """
    A chain of Set nodes using n8n's built-in expression regex replace.
    Only the top-N rules (longest phrases first) are wired to keep it visual.
    Use the Code-node workflow for the full ruleset.
    """
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
                    }]
                },
                "options": {}
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


def main() -> int:
    h = Humanizer()
    rules = h.dump_regex_rules()

    wf1 = build_code_node_workflow(rules)
    (OUT_DIR / "n8n_workflow_code_node.json").write_text(
        json.dumps(wf1, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    wf2 = build_regex_chain_workflow(rules, top_n=40)
    (OUT_DIR / "n8n_workflow_regex_chain.json").write_text(
        json.dumps(wf2, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {len(rules)} rules into:")
    print("  n8n/n8n_workflow_code_node.json    (recommended, full ruleset)")
    print("  n8n/n8n_workflow_regex_chain.json  (top-40 Set-node illustration)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
