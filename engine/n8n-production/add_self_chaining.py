#!/usr/bin/env python3
"""Add self-chaining to WFP0..WFP6: after the 'Advance to <next>' node, POST to the
next stage's webhook with {site_id, record_id}, so the pipeline runs autonomously
with no Airtable automation. WFP7 does NOT chain (Editor Review is a human gate).
Updates each workflow in n8n (PUT) and rewrites the repo JSON. Idempotent: skips a
workflow that already has a 'Trigger next stage' node.
"""
import json, urllib.request, os

N8N = "https://voyagerscontent.app.n8n.cloud"
PUB = os.environ["N8N_PUB"]
HOOK = N8N + "/webhook/galapagos-production/stage/"

# (repo file, workflow id, next-stage slug)
CHAIN = [
    ("WFP0_production_intake.json", "i8xtkx9GBw1aRdkP", "scoring"),
    ("WFP1_scoring.json",           "zJKqFEmA9FYDJYXh", "brief"),
    ("WFP2_brief.json",             "cFY7Tz5q2ih2UCvt", "draft"),
    ("WFP3_draft.json",             "eExgOTVFIoCuJb0D", "truthcheck"),
    ("WFP4_truthcheck.json",        "ZsrCHmeSCy8P4Wb2", "humanize"),
    ("WFP5_humanize.json",          "yh9kMFkbPY34vmVJ", "polish"),
    ("WFP6_polish.json",            "U0MrpTN3hv4RfNMI", "auditor"),
]
here = os.path.dirname(__file__)

def http_node(next_slug, pos):
    return {
      "parameters": {
        "method": "POST",
        "url": HOOK + next_slug,
        "sendBody": True,
        "specifyBody": "keypair",
        "bodyParameters": {"parameters": [
            {"name": "site_id", "value": "={{ $('Airtable Status Webhook').item.json.body.site_id }}"},
            {"name": "record_id", "value": "={{ $('Re-check and Claim (guarded)').item.json.id }}"},
        ]},
        "options": {},
      },
      "name": "Trigger next stage",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": pos,
      "onError": "continueRegularOutput",
    }

def put(wid, wf):
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": wf.get("settings", {"executionOrder": "v1"})}
    req = urllib.request.Request(N8N + "/api/v1/workflows/" + wid, data=json.dumps(body).encode(),
        headers={"X-N8N-API-KEY": PUB, "Content-Type": "application/json"}, method="PUT")
    try:
        r = json.load(urllib.request.urlopen(req)); return "ok id=" + str(r.get("id"))
    except urllib.error.HTTPError as e:
        return "ERROR %d %s" % (e.code, e.read().decode()[:200])

for fn, wid, nxt in CHAIN:
    path = os.path.join(here, fn)
    wf = json.load(open(path))
    if any(n["name"] == "Trigger next stage" for n in wf["nodes"]):
        print("%-30s already chained, skip" % fn); continue
    adv = [n for n in wf["nodes"] if n["name"].startswith("Advance to")]
    if not adv:
        print("%-30s NO advance node, skip" % fn); continue
    adv = adv[0]
    hn = http_node(nxt, [adv["position"][0] + 220, adv["position"][1]])
    wf["nodes"].append(hn)
    wf["connections"].setdefault(adv["name"], {"main": [[]]})
    # advance node currently terminal; wire its main[0] to the trigger
    wf["connections"][adv["name"]] = {"main": [[{"node": "Trigger next stage", "type": "main", "index": 0}]]}
    open(path, "w").write(json.dumps(wf, indent=2))
    print("%-30s + Trigger next stage -> /%s  | PUT %s" % (fn, nxt, put(wid, wf)))
