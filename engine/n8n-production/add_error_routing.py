#!/usr/bin/env python3
"""Make LLM failures route to Needs Attention instead of stalling the record.
For WFP1..WFP7: set the Anthropic node onError=continueRegularOutput (so a failed
call still emits an item), and enhance the Validate Output node to capture the
node error message. The existing Validate->If->Route to Needs Attention path then
parks the record with a real Last Error. Updates n8n (PUT) + rewrites repo JSON.
"""
import json, urllib.request, os
N8N = "https://voyagerscontent.app.n8n.cloud"
PUB = os.environ["N8N_PUB"]
WFS = [("WFP1_scoring.json","zJKqFEmA9FYDJYXh"),("WFP2_brief.json","cFY7Tz5q2ih2UCvt"),
       ("WFP3_draft.json","eExgOTVFIoCuJb0D"),("WFP4_truthcheck.json","ZsrCHmeSCy8P4Wb2"),
       ("WFP5_humanize.json","yh9kMFkbPY34vmVJ"),("WFP6_polish.json","U0MrpTN3hv4RfNMI"),
       ("WFP7_auditor.json","na9GWyR851UHSlbP")]
here = os.path.dirname(__file__)
NODEERR = ("raw=_o;\nconst nodeErr = ($json && $json.error) ? "
           "(typeof $json.error==='string' ? $json.error : ($json.error.message || JSON.stringify($json.error))) : '';\n")

def put(wid, wf):
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": wf.get("settings", {"executionOrder":"v1"})}
    req = urllib.request.Request(N8N+"/api/v1/workflows/"+wid, data=json.dumps(body).encode(),
        headers={"X-N8N-API-KEY": PUB, "Content-Type":"application/json"}, method="PUT")
    try: return "ok" if json.load(urllib.request.urlopen(req)).get("id") else "??"
    except urllib.error.HTTPError as e: return "ERR %d %s"%(e.code, e.read().decode()[:160])

for fn, wid in WFS:
    p = os.path.join(here, fn); wf = json.load(open(p)); changed = []
    for n in wf["nodes"]:
        if n["type"].endswith("langchain.anthropic"):
            n["onError"] = "continueRegularOutput"; changed.append("anthropic.onError")
        if n["name"] == "Validate Output":
            js = n["parameters"]["jsCode"]
            if "const nodeErr" not in js:
                js = js.replace("raw=_o;\n", NODEERR, 1)
                js = js.replace("return [{json:out}];",
                                "if(!out.ok && nodeErr) out.error='LLM node error: '+nodeErr;\nreturn [{json:out}];", 1)
                n["parameters"]["jsCode"] = js; changed.append("validator.nodeErr")
    open(p,"w").write(json.dumps(wf, indent=2))
    print("%-22s %-18s -> %s" % (fn, ",".join(changed) or "no-change", put(wid, wf)))
