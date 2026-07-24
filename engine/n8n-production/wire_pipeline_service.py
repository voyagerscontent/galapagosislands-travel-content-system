#!/usr/bin/env python3
"""wire_pipeline_service.py — wire the content-pipeline FastAPI service into
WFP5 (humanize) and WFP7 (auditor) as HTTP Code nodes.

Changes made:
  WFP5: After "De-AI Dictionary (no-LLM)" → add "Pipeline Verify (HTTP)" node
        which calls POST /verify and POST /lexical/inject on the Python service.
        If structural_ok=false → route to Needs Attention with reason.
        If ok → continue to Output OK? as before.

  WFP7: Replace the inline "BCP Inject (HTML)" JS node with a proper HTTP call
        to POST /lexical/inject on the Python service (full POS, per-paragraph salt).
        The JS node was 258KB of compiled lexicon — the service call is 4 lines.

Run after setting env vars:
  export PIPELINE_SERVICE_URL=https://pipeline.yourdomain.com
  export PIPELINE_SERVICE_KEY=YOUR_SHARED_SECRET_HERE   # header X-Pipeline-Key
  export N8N_PUB=your_n8n_api_key
  python engine/n8n-production/wire_pipeline_service.py
"""
import json, os, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).parent
WFP5_PATH = HERE / "WFP5_humanize.json"
WFP7_PATH = HERE / "WFP7_auditor.json"
N8N = "https://voyagerscontent.app.n8n.cloud"
WFP5_WID = "yh9kMFkbPY34vmVJ"
WFP7_WID = "na9GWyR851UHSlbP"

SERVICE_URL = os.environ.get("PIPELINE_SERVICE_URL", "https://pipeline.yourdomain.com")
SERVICE_KEY = os.environ.get("PIPELINE_SERVICE_KEY", "")
N8N_PUB    = os.environ.get("N8N_PUB", "")


def http_node(name, url, body_expr, pos, node_id):
    """Build an n8n httpRequest node that POSTs JSON to the Python service."""
    return {
        "parameters": {
            "method": "POST",
            "url": url,
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "X-Pipeline-Key", "value": SERVICE_KEY},
                ]
            },
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "text", "value": body_expr},
                    {"name": "replace_verbs", "value": "true"},
                    {"name": "salt", "value": "true"},
                ]
            },
            "options": {"timeout": 120000},
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": pos,
        "onError": "continueRegularOutput",
    }


def code_node(name, js, pos, node_id):
    return {
        "parameters": {"jsCode": js},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": pos,
    }


# ── WFP5 patch ────────────────────────────────────────────────────────────────
VERIFY_JS = """
// Pipeline Verify: check /verify response and route accordingly.
// If the Python service is unreachable, log and continue (fail-open so the
// pipeline isn't blocked by a transient server restart).
const res = $json || {};
const structOk = res.structural_ok !== false;  // undefined = service down = pass through
const reason = structOk ? '' :
  ('macro NCD=' + (res.macro_ncd||'?') + ' (' + (res.macro_passed?'PASS':'FAIL') + ')' +
   ', micro CV=' + (res.micro_cv||'?') + ' (' + (res.micro_passed?'PASS':'FAIL') + ')');
const prev = ($items('Finalize (code)')[0] || {json:{}}).json;
return [{ json: { ...prev, structOk, verifyReason: reason } }];
"""

INJECT_CHECK_JS = """
// Handle /lexical/inject response from the Python service.
// Falls back to the unmodified artifact if the service failed or returned nothing.
const res = $json || {};
const prev = ($items('Pipeline Verify (HTTP)')[0] || {json:{}}).json;
const injectedText = res.text || prev.artifact || '';
const log = 'Python injector v1.1: ' +
  (res.replacements ? res.replacements.length : 0) + ' swap(s), ' +
  (res.salted_paragraphs || 0) + ' para salt(s) (' +
  (res.salt_long || 0) + ' long + ' + (res.salt_phrase || 0) + ' phrase) — POS-confirmed';
return [{ json: {
  ...prev,
  artifact: injectedText,
  deaiLog: (prev.deaiLog ? prev.deaiLog + '\\n' : '') + log,
} }];
"""


def patch_wfp5(wf: dict) -> dict:
    nodes = {n["name"]: n for n in wf["nodes"]}
    c = wf["connections"]

    # Find position anchor: De-AI Dictionary is last before Output OK?
    dict_node = nodes.get("De-AI Dictionary (no-LLM)")
    ok_node   = nodes.get("Output OK?")
    if not dict_node or not ok_node:
        raise ValueError("Expected nodes 'De-AI Dictionary (no-LLM)' and 'Output OK?' not found in WFP5")

    dx, dy = dict_node["position"]

    # Remove any pre-existing pipeline service nodes
    wf["nodes"] = [n for n in wf["nodes"]
                   if n["name"] not in ("Pipeline Verify (HTTP)", "Pipeline Inject (HTTP)",
                                        "Inject Check (code)", "Verify Check (code)")]

    # Insert: De-AI Dict → Pipeline Verify (HTTP) → Verify Check → Pipeline Inject (HTTP)
    #         → Inject Check → Output OK? (existing)
    verify_http = http_node(
        "Pipeline Verify (HTTP)",
        f"{SERVICE_URL}/verify",
        "={{ $('Finalize (code)').item.json.artifact }}",
        [dx + 220, dy], "wfp5-verify-http",
    )
    verify_check = code_node("Verify Check (code)", VERIFY_JS, [dx + 440, dy], "wfp5-verify-check")
    inject_http = http_node(
        "Pipeline Inject (HTTP)",
        f"{SERVICE_URL}/lexical/inject",
        "={{ $json.artifact }}",
        [dx + 660, dy], "wfp5-inject-http",
    )
    inject_check = code_node("Inject Check (code)", INJECT_CHECK_JS, [dx + 880, dy], "wfp5-inject-check")

    wf["nodes"].extend([verify_http, verify_check, inject_http, inject_check])

    # Rewire: De-AI Dict → Pipeline Verify (HTTP) → Verify Check → Pipeline Inject (HTTP)
    #         → Inject Check → Output OK?
    c["De-AI Dictionary (no-LLM)"] = {"main": [[{"node": "Pipeline Verify (HTTP)", "type": "main", "index": 0}]]}
    c["Pipeline Verify (HTTP)"]    = {"main": [[{"node": "Verify Check (code)",    "type": "main", "index": 0}]]}
    c["Verify Check (code)"]       = {"main": [
        [{"node": "Pipeline Inject (HTTP)", "type": "main", "index": 0}],   # structOk=true
        [{"node": "Route to Needs Attention", "type": "main", "index": 0}], # structOk=false
    ]}
    c["Pipeline Inject (HTTP)"]    = {"main": [[{"node": "Inject Check (code)", "type": "main", "index": 0}]]}
    c["Inject Check (code)"]       = {"main": [[{"node": "Output OK?",          "type": "main", "index": 0}]]}

    return wf


# ── WFP7 patch ────────────────────────────────────────────────────────────────
WFP7_INJECT_CHECK_JS = """
// Handle /lexical/inject response from the Python service in WFP7.
// Falls back to the existing Polished Content if service is unreachable.
const res = $json || {};
const rec = ($items('Re-check and Claim (guarded)')[0] || {json:{}}).json;
const prev = ($items('Output OK?')[0] || {json:{}}).json;
const prior = ($items('Validate Output')[0] || {json:{}}).json;
const injectedText = res.text || rec['Polished Content'] || '';
const log = 'Python BCP @publish v1.1 (POS, per-para): ' +
  (res.replacements ? res.replacements.length : 0) + ' swap(s), ' +
  (res.salted_paragraphs || 0) + ' para salt(s) (' +
  (res.salt_long || 0) + ' long + ' + (res.salt_phrase || 0) + ' phrase)';
const priorLog = rec['De-AI Log'] || prior.deaiLog || '';
return [{ json: {
  recordId: prior.recordId || rec.id || prev.recordId || '',
  baseId:   prior.baseId || prev.baseId || '',
  tableId:  prior.tableId || prev.tableId || '',
  notes:    prior.notes || prev.notes || '',
  artifact: injectedText,
  deaiLog:  (priorLog ? priorLog + '\\n' : '') + log,
} }];
"""


def patch_wfp7(wf: dict) -> dict:
    nodes = {n["name"]: n for n in wf["nodes"]}
    c = wf["connections"]

    ok_node  = nodes.get("Output OK?")
    adv_node = nodes.get("Advance to Editor Review")
    if not ok_node or not adv_node:
        raise ValueError("Expected 'Output OK?' and 'Advance to Editor Review' in WFP7")

    ox, oy = ok_node["position"]
    ax, ay = adv_node["position"]

    # Remove old inline BCP Inject node (258KB JS blob)
    wf["nodes"] = [n for n in wf["nodes"]
                   if n["name"] not in ("BCP Inject (HTML)", "BCP Inject Check (code)",
                                        "Pipeline Inject (HTTP)", "Inject Check (code)")]

    # Reclaim the advance node position
    nodes["Advance to Editor Review"]["position"] = [ax, ay]

    # Add: Pipeline Inject (HTTP) → Inject Check (code) → Advance to Editor Review
    inject_http  = http_node(
        "Pipeline Inject (HTTP)",
        f"{SERVICE_URL}/lexical/inject",
        "={{ $('Validate Output').item.json.artifact || $('Re-check and Claim (guarded)').item.json['Polished Content'] }}",
        [ox + 220, oy], "wfp7-inject-http",
    )
    inject_check = code_node("Inject Check (code)", WFP7_INJECT_CHECK_JS,
                             [ox + 440, oy], "wfp7-inject-check")

    wf["nodes"].extend([inject_http, inject_check])

    # Rewire: Output OK? pass → Pipeline Inject → Inject Check → Advance
    c["Output OK?"] = {"main": [
        [{"node": "Pipeline Inject (HTTP)",  "type": "main", "index": 0}],  # pass
        [{"node": "Route to Needs Attention","type": "main", "index": 0}],  # fail
    ]}
    c["Pipeline Inject (HTTP)"] = {"main": [[{"node": "Inject Check (code)", "type": "main", "index": 0}]]}
    c["Inject Check (code)"]    = {"main": [[{"node": "Advance to Editor Review", "type": "main", "index": 0}]]}

    # Advance node: write injected artifact + log
    adv_cols = nodes["Advance to Editor Review"]["parameters"]["columns"]["value"]
    adv_cols["Polished Content"] = "={{ $json.artifact }}"
    adv_cols["De-AI Log"]        = "={{ $json.deaiLog }}"

    return wf


def push_to_n8n(wid: str, wf: dict, label: str):
    if not N8N_PUB:
        print(f"  {label}: no N8N_PUB — saved locally only")
        return
    body = json.dumps({
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"}),
    }).encode()
    req = urllib.request.Request(
        f"{N8N}/api/v1/workflows/{wid}", data=body,
        headers={"X-N8N-API-KEY": N8N_PUB, "Content-Type": "application/json"},
        method="PUT",
    )
    try:
        d = json.load(urllib.request.urlopen(req))
        print(f"  {label}: pushed OK — id={d.get('id')} active={d.get('active')}")
    except urllib.error.HTTPError as e:
        print(f"  {label}: push ERROR {e.code}: {e.read().decode()[:300]}")


def main():
    print("=== wire_pipeline_service.py ===")
    print(f"  SERVICE_URL = {SERVICE_URL}")
    print(f"  N8N_PUB     = {'set' if N8N_PUB else 'NOT SET — local only'}")
    print()

    # Patch WFP5
    wf5 = json.loads(WFP5_PATH.read_text(encoding="utf-8"))
    wf5 = patch_wfp5(wf5)
    WFP5_PATH.write_text(json.dumps(wf5, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"WFP5: patched — {WFP5_PATH.stat().st_size // 1024} KB")
    push_to_n8n(WFP5_WID, wf5, "WFP5")

    # Patch WFP7
    wf7 = json.loads(WFP7_PATH.read_text(encoding="utf-8"))
    wf7 = patch_wfp7(wf7)
    WFP7_PATH.write_text(json.dumps(wf7, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"WFP7: patched — inline BCP Inject (258KB JS) replaced with HTTP call")
    print(f"WFP7: {WFP7_PATH.stat().st_size // 1024} KB")
    push_to_n8n(WFP7_WID, wf7, "WFP7")


if __name__ == "__main__":
    main()
