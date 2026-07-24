#!/usr/bin/env python3
"""WFP5 Burstiness & Structure HARD gate with bounded retry -> advisory (no server).

Option A (all in n8n, no DigitalOcean): ports the macro paragraph-length burstiness
(gzip NCD) + micro sentence-CV check to a JS code node. After the humanized artifact
is produced (post De-AI Dictionary), the gate runs:

  pass  (macro NCD >= 0.28 AND sentence CV >= 0.45) -> advance to Polishing
  fail  & Burstiness Retries < 3 -> bump the counter, clear Humanized Content, and
        re-fire the humanize webhook (the LLM re-writes with the burstiness-aware
        prompt) — a bounded self-retry, same shape as WFP6's Re-trigger.
  fail  & Burstiness Retries >= 3 -> ADVISORY: advance anyway, writing the reason to
        the "Burstiness Notes" field for the editor. Never blocks forever.

Deterministic, no LLM in the gate itself, no external service.

  De-AI Dictionary -> Burstiness Gate (code) -> Retry Burstiness? (if)
      true  -> Bump Burstiness (Airtable) -> Re-humanize (HTTP /humanize)
      false -> Output OK? (existing; Advance writes Burstiness Notes + resets counter)
"""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP5_humanize.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "yh9kMFkbPY34vmVJ"
HUMANIZE_WEBHOOK = N8N + "/webhook/galapagos-production/stage/humanize"
NEW = ("Burstiness Gate (code)", "Retry Burstiness?", "Bump Burstiness", "Re-humanize")

GATE_JS = r"""
const zlib = require('zlib');
function C(b){ return zlib.gzipSync(b, {level: 9}).length; }
function ncd(x, y){ const cx=C(x), cy=C(y), cxy=C(Buffer.concat([x,y])); const d=Math.max(cx,cy); return d ? (cxy-Math.min(cx,cy))/d : 0; }
function paragraphs(t){ return String(t||'').trim().split(/\n\s*\n+/).map(p=>p.trim()).filter(Boolean); }
function proseNoTables(t){ return String(t||'').replace(/<table[\s\S]*?<\/table>/gi,' ').replace(/(^|\n)\s*\|.*\|.*(?=\n|$)/g,' ').replace(/<[^>]+>/g,' ').replace(/\[(?:source|VERIFY|human)[^\]]*\]/g,' '); }
function paraShape(sec){ const sh=[]; for(const p of paragraphs(sec)){ if(/^#{1,6}\s/.test(p)) continue; const t=p.split(/\s+/).filter(Boolean).length; const s=Math.max(1, p.split(/(?<=[.!?])\s+/).filter(x=>x.trim().split(/\s+/).length>=3).length); sh.push([t,s]); } return sh; }
function sbytes(sh){ const b=[]; for(const p of sh){ b.push(Buffer.alloc(p[0],65)); b.push(Buffer.alloc(p[1],66)); b.push(Buffer.from('\n')); } return Buffer.concat(b); }
function baseline(sh){ const n=sh.length||1, at=Math.max(1,Math.round(sh.reduce((a,x)=>a+x[0],0)/n)), as=Math.max(1,Math.round(sh.reduce((a,x)=>a+x[1],0)/n)); return sbytes(sh.map(()=>[at,as])); }
function macroEval(sec){ const sh=paraShape(sec); if(sh.length<3) return {passed:true, ncd:1, paras:sh.length}; const score=ncd(sbytes(sh), baseline(sh)); return {passed: score>=0.28, ncd: Math.round(score*1000)/1000, paras: sh.length}; }
function microCV(sec){ const p=proseNoTables(sec); const s=p.split(/(?<=[.!?])\s+/).map(x=>x.trim()).filter(x=>x.split(/\s+/).filter(Boolean).length>=3); if(s.length<2) return 1; const L=s.map(x=>x.split(/\s+/).filter(Boolean).length); const m=L.reduce((a,b)=>a+b,0)/L.length; if(!m) return 0; const v=L.reduce((a,b)=>a+(b-m)*(b-m),0)/L.length; return Math.sqrt(v)/m; }

const CV_MIN = 0.45;
const it = $json || {};
const rec = ($items('Re-check and Claim (guarded)')[0] || {json:{}}).json;
if (!it.ok) {   // humanize/dictionary already failed upstream — don't gate; let Output OK? route it
  return [{ json: Object.assign({}, it, { action: 'pass', burstinessNote: '' }) }];
}
const art = String(it.artifact || '');
const retries = Number(rec['Burstiness Retries'] || 0);
const m = macroEval(art);
const cv = microCV(art);
const bok = m.passed && cv >= CV_MIN;
const action = bok ? 'pass' : (retries < 3 ? 'retry' : 'advisory');
const detail = 'macro NCD ' + m.ncd + ' (min 0.28), sentence CV ' + cv.toFixed(2) + ' (min ' + CV_MIN + '), ' + m.paras + ' paragraphs';
const note = action === 'advisory' ? ('ADVISORY — burstiness below threshold after 3 retries: ' + detail)
           : (bok ? '' : ('retry ' + (retries + 1) + '/3: ' + detail));
return [{ json: Object.assign({}, it, {
  action: action, burstinessRetries: retries,
  macroNcd: m.ncd, microCv: Math.round(cv * 100) / 100, burstinessNote: note
}) }];
"""


def main():
    wf = json.load(open(WF, encoding="utf-8"))
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in NEW]
    for nm in NEW:
        wf["connections"].pop(nm, None)
    nodes = {n["name"]: n for n in wf["nodes"]}

    ax, ay = nodes["Output OK?"]["position"]
    for nm in ("Output OK?", "Export to Drive", "Advance to Polishing", "Route to Needs Attention"):
        if nm in nodes:
            nodes[nm]["position"] = [nodes[nm]["position"][0] + 400, nodes[nm]["position"][1]]

    def anode(name, params, pos, nid, ntype="n8n-nodes-base.code", tv=2):
        return {"parameters": params, "id": nid, "name": name, "type": ntype, "typeVersion": tv, "position": pos}

    gate = anode("Burstiness Gate (code)", {"jsCode": GATE_JS}, [ax - 40, ay], "wfp5-burst-gate")
    retry_if = anode("Retry Burstiness?", {"conditions": {"string": [
        {"value1": "={{ $json.action }}", "value2": "retry"}]}},
        [ax + 140, ay + 160], "wfp5-burst-retry", ntype="n8n-nodes-base.if", tv=1)
    bump = anode("Bump Burstiness", {
        "operation": "update",
        "base": {"__rl": True, "mode": "id", "value": "={{ $json.baseId }}"},
        "table": {"__rl": True, "mode": "id", "value": "={{ $json.tableId }}"},
        "columns": {"mappingMode": "defineBelow", "matchingColumns": ["id"], "value": {
            "id": "={{ $json.recordId }}",
            "Status": "Humanizing",
            "Humanized Content": "",
            "Burstiness Retries": "={{ $json.burstinessRetries + 1 }}",
        }}, "options": {}},
        [ax + 320, ay + 160], "wfp5-burst-bump", ntype="n8n-nodes-base.airtable", tv=2.1)
    # copy the Airtable credential from an existing Airtable node
    _at = next((n for n in wf["nodes"] if n["type"].endswith("airtable") and n.get("credentials")), None)
    if _at:
        bump["credentials"] = _at["credentials"]
    rehum = anode("Re-humanize", {
        "method": "POST", "url": HUMANIZE_WEBHOOK, "sendBody": True, "specifyBody": "keypair",
        "bodyParameters": {"parameters": [
            {"name": "site_id", "value": "={{ $('Airtable Status Webhook').item.json.body.site_id }}"},
            {"name": "record_id", "value": "={{ $('Burstiness Gate (code)').item.json.recordId }}"},
        ]}, "options": {}},
        [ax + 500, ay + 160], "wfp5-burst-rehum", ntype="n8n-nodes-base.httpRequest", tv=4.2)

    wf["nodes"] += [gate, retry_if, bump, rehum]

    c = wf["connections"]
    c["De-AI Dictionary (no-LLM)"] = {"main": [[{"node": "Burstiness Gate (code)", "type": "main", "index": 0}]]}
    c["Burstiness Gate (code)"] = {"main": [[{"node": "Retry Burstiness?", "type": "main", "index": 0}]]}
    c["Retry Burstiness?"] = {"main": [
        [{"node": "Bump Burstiness", "type": "main", "index": 0}],       # retry
        [{"node": "Output OK?", "type": "main", "index": 0}],            # pass / advisory
    ]}
    c["Bump Burstiness"] = {"main": [[{"node": "Re-humanize", "type": "main", "index": 0}]]}

    # artifact + note now come from the gate node
    for nm in ("Export to Drive", "Advance to Polishing"):
        s = json.dumps(nodes[nm]["parameters"]).replace("$('De-AI Dictionary (no-LLM)')", "$('Burstiness Gate (code)')")
        nodes[nm]["parameters"] = json.loads(s)
    adv = nodes["Advance to Polishing"]["parameters"]["columns"]["value"]
    adv["Burstiness Notes"] = "={{ $('Burstiness Gate (code)').item.json.burstinessNote }}"
    adv["Burstiness Retries"] = "={{ 0 }}"

    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"WFP5: Burstiness & Structure gate added (hard, 3 retries -> advisory). {os.path.getsize(WF)//1024} KB")

    pub = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not pub:
        print("no key — local only."); return
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
