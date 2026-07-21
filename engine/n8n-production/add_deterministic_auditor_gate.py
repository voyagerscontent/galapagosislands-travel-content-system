#!/usr/bin/env python3
"""Insert the deterministic QA gate into WFP7 (Auditor Review) — code, not LLM.

The auditor used to hand every pass/fail to the language model. The model
miscounted meta length, false-positived on Fleet's amenity tables, and could
override its own correct grounding — the exact "LLMs cannot count, use code
gates" failure the repo already learned once. This makes every OBJECTIVE check
deterministic and runs it BEFORE the model:

    Re-check and Claim ─► QA Gate (code) ─► Gate OK?
                                              ├─ false ─► Route to Needs Attention   (LLM never runs)
                                              └─ true  ─► Run Stage Agent (LLM) ─► Validate Output ─► …

A code FAIL cannot be overridden by the model and does not spend a token. The
model that runs after a PASS judges only the irreducibly semantic things
(truth-grounding, Juan voice, fidelity) — it never sees an objective violation
because the gate already caught it.

The gate logic is engine/n8n-production/qa_gate.js (single source of truth).
This applier embeds it verbatim into the node. Edit the .js, re-run this,
commit. Never hand-edit the node in n8n.
"""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP7_auditor.json")
GATE_JS = os.path.join(HERE, "qa_gate.js")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "na9GWyR851UHSlbP"

# n8n glue appended after the embedded gate() definition. Reads the claimed
# record ($json) and the registry (Lookup Site) and emits either a pass-through
# record (record intact so the LLM still reads Polished/Draft Content) or the
# {recordId, baseId, tableId, error} shape Route to Needs Attention consumes.
GLUE = r"""
// ── n8n glue ───────────────────────────────────────────────────────────────
const rec  = $json || {};
const site = $items('Lookup Site (registry)')[0] ? $items('Lookup Site (registry)')[0].json : {};
const recordId = rec.id || '';
const baseId = site['Base ID'] || '';
const tableId = site['Table ID'] || '';
const html = rec['Polished Content'] || '';
const res = gate(html, rec);
if (res.pass) {
  // pass the whole record through, plus routing metadata for downstream nodes
  return [{ json: Object.assign({}, rec, {
    _gate_ok: true, recordId, baseId, tableId,
    gateNotes: (res.notes || []).join(' | ')
  }) }];
}
return [{ json: {
  _gate_ok: false, recordId, baseId, tableId,
  error: 'QA GATE FAIL (deterministic, measured in code): ' + res.fails.join('  •  '),
  notes: (res.notes || []).join(' | ')
}}];
"""


def build_gate_node_code():
    src = open(GATE_JS, encoding="utf-8").read()
    # drop the CommonJS export line — n8n code node has no module system
    src = "\n".join(l for l in src.splitlines() if "module.exports" not in l)
    return src + "\n" + GLUE


def main():
    wf = json.load(open(WF, encoding="utf-8"))
    nodes = {n["name"]: n for n in wf["nodes"]}

    # anchor node positions relative to the LLM node
    agent = nodes["Run Stage Agent"]
    ax, ay = agent["position"]

    gate_node = {
        "parameters": {"jsCode": build_gate_node_code()},
        "id": "qa-gate-code-0001",
        "name": "QA Gate (code)",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [ax - 320, ay],
    }
    gate_if = {
        "parameters": {"conditions": {"boolean": [
            {"value1": "={{ $json._gate_ok }}", "value2": True}
        ]}},
        "id": "qa-gate-if-0001",
        "name": "Gate OK?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [ax - 160, ay],
    }
    # avoid duplicate insert on re-run
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in ("QA Gate (code)", "Gate OK?")]
    wf["nodes"].extend([gate_node, gate_if])

    c = wf["connections"]
    # Re-check and Claim now feeds the gate (was: -> Run Stage Agent)
    c["Re-check and Claim (guarded)"] = {"main": [[{"node": "QA Gate (code)", "type": "main", "index": 0}]]}
    c["QA Gate (code)"] = {"main": [[{"node": "Gate OK?", "type": "main", "index": 0}]]}
    # Gate OK? true -> LLM ; false -> Needs Attention (LLM skipped)
    c["Gate OK?"] = {"main": [
        [{"node": "Run Stage Agent", "type": "main", "index": 0}],
        [{"node": "Route to Needs Attention", "type": "main", "index": 0}],
    ]}
    # Run Stage Agent -> Validate Output stays as-is

    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("WFP7 rewired: Re-check -> QA Gate (code) -> Gate OK? -> {LLM | Needs Attention}")

    pub = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not pub:
        print("No N8N_PUB/N8N_API_KEY in env — wrote local JSON only, did not push.")
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
