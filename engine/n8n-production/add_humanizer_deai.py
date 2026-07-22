#!/usr/bin/env python3
"""Wire the deterministic de-AI layer into WFP5 (Humanizing).

New flow (was: Validate Output -> Output OK? -> Export/Needs Attention):

  Validate Output
    -> AI De-Signal (code)         clean() invisibles/markup-leak; detect() signals per paragraph
    -> Reconstruct?  (if)
         false -> Finalize (code)
         true  -> Reconstruct (Andre<->Juan, LLM)   rewrite ONLY flagged paragraphs
               -> Merge & Verify (code)             splice back + FACT-PRESERVATION gate + re-detect
               -> Finalize (code)
    -> Finalize (code)             single stable reference for the artifact
    -> Output OK? -> Export to Drive -> Advance to Polishing | Route to Needs Attention

Everything objective is CODE: the invisible-char cleanup, the signal detection, and
the fact-preservation gate (numbers/prices/dates/markers extracted before the rewrite
must survive it — any rewrite that drops one is REJECTED and the original paragraph
kept, so a de-AI pass can never corrupt a fact — the safe answer to the CLSA
translate+summarize attack, which demonstrably destroys facts). The LLM only rewrites.

Gate + blocklist come from ai_signals.js / ai_signal_blocklist.json (single source of
truth). Edit those, re-run this, commit. Never hand-edit the nodes in n8n.
"""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP5_humanize.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "yh9kMFkbPY34vmVJ"

def gate_src():
    src = open(os.path.join(HERE, "ai_signals.js"), encoding="utf-8").read()
    src = "\n".join(l for l in src.splitlines() if "module.exports" not in l)
    bl = open(os.path.join(HERE, "ai_signal_blocklist.json"), encoding="utf-8").read()
    return src + "\nconst BLOCKLIST = " + bl + ";\n"

# ── code node bodies ────────────────────────────────────────────────────────
DESIGNAL = gate_src() + r"""
// input: Validate Output -> {recordId,baseId,tableId,ok,error,artifact}
const v = $json || {};
if (!v.ok) { return [{ json: Object.assign({}, v, { reconstruct: false, signals: '' }) }]; }
const c = clean(v.artifact);
const art = c.text;
const paras = art.split(/\n{2,}/);
const flagged = [];
paras.forEach((p, i) => {
  if (p.trim().length < 40) return;
  const d = detect(p, BLOCKLIST);
  const bad = d.fails.filter(f => /TIER-A|em-dash/.test(f));
  if (bad.length) flagged.push({ idx: i, text: p, reasons: bad });
});
const whole = detect(art, BLOCKLIST);
return [{ json: Object.assign({}, v, {
  artifact: art, paras, flagged,
  reconstruct: flagged.length > 0,
  signals: whole.fails.join(' | '),
  cleaned: (c.strippedInvisible + c.normalizedSpaces + c.markupLeaks)
}) }];
"""

MERGE = gate_src() + r"""
// splice the LLM's rewrites back in, but ONLY where every fact survived.
const base = $('AI De-Signal (code)').item.json;
let raw = Array.isArray($json.content) ? $json.content.filter(b=>b.type==='text').map(b=>b.text).join('')
        : ($json.message && $json.message.content ? $json.message.content : ($json.text||''));
raw = (raw||'').trim();
if (raw.startsWith('```')) { const f = raw.match(/^```(?:json)?\s*([\s\S]*?)```\s*$/); if (f) raw = f[1].trim(); }
const s0 = raw.indexOf('{'), e0 = raw.lastIndexOf('}'); if (s0!==-1 && e0>s0) raw = raw.slice(s0, e0+1);
let rewrites = {};
try { const p = JSON.parse(raw); (p.rewrites||[]).forEach(r => { if (r && r.idx!=null) rewrites[r.idx] = String(r.text||''); }); } catch(e) {}

// FACT-PRESERVATION GATE (deterministic): numbers, $ amounts, %, 4-digit years,
// and internal markers present before the rewrite MUST all survive it.
function facts(t){
  return new Set((String(t).match(/\$[\d.,]+|\b\d+(?:[.,]\d+)?\s?%|\b\d{4}\b|\b\d+(?:[.,]\d+)?\b|\[(?:source|VERIFY|verify|human)[^\]]*\]/gi) || []).map(x=>x.trim()));
}
const paras = base.paras.slice();
const rejected = [];
for (const k of Object.keys(rewrites)) {
  const i = Number(k);
  const before = facts(base.paras[i]); const after = facts(rewrites[k]);
  const missing = [...before].filter(x => !after.has(x));
  if (missing.length) { rejected.push('para ' + i + ' would drop: ' + missing.slice(0,6).join(', ')); }
  else { paras[i] = clean(rewrites[k]).text; }   // accept only when facts intact
}
let art = clean(paras.join('\n\n')).text;
const final = detect(art, BLOCKLIST);
return [{ json: {
  recordId: base.recordId, baseId: base.baseId, tableId: base.tableId,
  ok: true, error: '', artifact: art,
  signals: final.fails.join(' | '),
  factGuard: rejected.length ? ('kept original for: ' + rejected.join(' ; ')) : 'all rewrites preserved facts'
} }];
"""

FINALIZE = r"""
// single stable reference for the finalized artifact (both paths converge here)
const j = $json || {};
return [{ json: {
  recordId: j.recordId || '', baseId: j.baseId || '', tableId: j.tableId || '',
  ok: j.ok === true, error: j.error || '', artifact: j.artifact || '',
  signals: j.signals || '', factGuard: j.factGuard || ''
} }];
"""

RECON_PROMPT = (
  "You reconstruct FLAGGED paragraphs of a Galápagos travel guide to strip AI-writing "
  "signals while keeping every fact exact. Method — a two-voice pass: ANDRE (a colleague) "
  "asks the plain question a reader would ask about the paragraph; JUAN (Galápagos advisor) "
  "answers it in his own voice using ONLY the facts already in that paragraph. Write each "
  "paragraph as Juan's answer.\n"
  "HARD RULES:\n"
  "• Keep every number, price ($), percentage, date/year, place name and [source:]/[VERIFY]/"
  "[human:] marker EXACTLY as written. Never add, drop, or change a fact (a code gate rejects "
  "any rewrite that loses one).\n"
  "• NO em-dashes (—). Use commas, periods, colons, or parentheses.\n"
  "• Vary sentence length on purpose: pair a short, punchy sentence with a longer one; a "
  "fragment is fine. Never a uniform rhythm.\n"
  "• Never use: delve, tapestry, cornerstone, pivotal, multifaceted, paradigm, robust, "
  "holistic, seamless, vibrant, bustling, myriad, plethora, underscore, showcase, foster, "
  "garner, leverage, elevate, unleash, moreover, furthermore, 'it is worth noting', 'plays a "
  "crucial role', 'a testament to', 'in conclusion', 'to summarize'. Say the plain thing.\n"
  "• Answer-first, specifics over adjectives, Juan's candid voice.\n\n"
  "FLAGGED PARAGRAPHS (JSON — each has idx, text, reasons):\n"
  "{{ JSON.stringify($('AI De-Signal (code)').item.json.flagged) }}\n\n"
  "Return STRICT JSON {\"rewrites\":[{\"idx\":<number>,\"text\":\"<rewritten paragraph>\"}]}."
)


def node(name, ntype, pos, params, tv=1, nid=None):
    return {"parameters": params, "id": nid or name.lower().replace(" ", "-").replace("(", "").replace(")", "")[:36],
            "name": name, "type": ntype, "typeVersion": tv, "position": pos}


def main():
    wf = json.load(open(WF, encoding="utf-8"))
    nodes = {n["name"]: n for n in wf["nodes"]}
    agent = nodes["Run Stage Agent"]
    ax, ay = agent["position"]

    # model + credential from the existing anthropic node, so Reconstruct matches
    a_params = json.loads(json.dumps(agent["parameters"]))
    a_params["messages"] = {"values": [{"content": RECON_PROMPT}]}
    a_params.setdefault("options", {})["maxTokens"] = 8000
    recon = node("Reconstruct (Andre-Juan)", agent["type"], [ax + 200, ay + 200], a_params,
                 tv=agent.get("typeVersion", 1), nid="recon-andre-juan")
    recon["credentials"] = agent.get("credentials", {})

    new = [
        node("AI De-Signal (code)", "n8n-nodes-base.code", [1180, 300], {"jsCode": DESIGNAL}, tv=2, nid="ai-de-signal"),
        node("Reconstruct?", "n8n-nodes-base.if", [1340, 300],
             {"conditions": {"boolean": [{"value1": "={{ $json.reconstruct }}", "value2": True}]}}, tv=1, nid="reconstruct-if"),
        recon,
        node("Merge & Verify (code)", "n8n-nodes-base.code", [1660, 400], {"jsCode": MERGE}, tv=2, nid="merge-verify"),
        node("Finalize (code)", "n8n-nodes-base.code", [1840, 300], {"jsCode": FINALIZE}, tv=2, nid="finalize-deai"),
    ]
    # shift the tail right so it doesn't overlap the inserted nodes
    for nm in ("Output OK?", "Export to Drive", "Advance to Polishing", "Route to Needs Attention"):
        nodes[nm]["position"] = [nodes[nm]["position"][0] + 900, nodes[nm]["position"][1]]

    wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in
                   ("AI De-Signal (code)", "Reconstruct?", "Reconstruct (Andre-Juan)", "Merge & Verify (code)", "Finalize (code)")]
    wf["nodes"].extend(new)

    c = wf["connections"]
    c["Validate Output"] = {"main": [[{"node": "AI De-Signal (code)", "type": "main", "index": 0}]]}
    c["AI De-Signal (code)"] = {"main": [[{"node": "Reconstruct?", "type": "main", "index": 0}]]}
    c["Reconstruct?"] = {"main": [
        [{"node": "Reconstruct (Andre-Juan)", "type": "main", "index": 0}],
        [{"node": "Finalize (code)", "type": "main", "index": 0}],
    ]}
    c["Reconstruct (Andre-Juan)"] = {"main": [[{"node": "Merge & Verify (code)", "type": "main", "index": 0}]]}
    c["Merge & Verify (code)"] = {"main": [[{"node": "Finalize (code)", "type": "main", "index": 0}]]}
    c["Finalize (code)"] = {"main": [[{"node": "Output OK?", "type": "main", "index": 0}]]}
    # Output OK? true/false connections stay (Export / Needs Attention)

    # repoint artifact references from Validate Output -> Finalize (code)
    for nm in ("Export to Drive", "Advance to Polishing"):
        s = json.dumps(nodes[nm]["parameters"])
        s = s.replace("$('Validate Output')", "$('Finalize (code)')")
        nodes[nm]["parameters"] = json.loads(s)
    # Route to Needs Attention reads $json (flows from Output OK? = Finalize's item) — fine.

    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("WFP5 rewired with de-AI gate + Andre<->Juan reconstruction + fact-preservation.")

    pub = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not pub:
        print("no N8N key — wrote local JSON only.")
        return
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})}
    req = urllib.request.Request(N8N + "/api/v1/workflows/" + WID, data=json.dumps(body).encode(),
                                 headers={"X-N8N-API-KEY": pub, "Content-Type": "application/json"}, method="PUT")
    try:
        d = json.load(urllib.request.urlopen(req))
        print("pushed to n8n:", "ok" if d.get("id") else "??", "| active:", d.get("active"))
    except urllib.error.HTTPError as e:
        print("push ERR %d %s" % (e.code, e.read().decode()[:300]))


if __name__ == "__main__":
    main()
