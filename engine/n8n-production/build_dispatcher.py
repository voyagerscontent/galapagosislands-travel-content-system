#!/usr/bin/env python3
"""WFPD Dispatcher — n8n polls Airtable and starts work itself. No human, no Claude, no UI click.

Why this exists: the chain was already autonomous once triggered, but SOMETHING had to fire the
first webhook, and that something was a person running curl. Airtable's Web API cannot create an
automation, so the documented UI automation was a manual setup step that never got done. n8n can
poll instead — which puts the whole trigger inside n8n, where the rest of the pipeline lives.

Runs on a schedule and does exactly two things per site in the registry:

  1. Status = Backlog                      -> POST .../stage/intake     (start the chain)
  2. Status = Brief Ready
     AND MarketMuse Score is not empty
     AND Brief Content is not empty        -> set Status = Drafting, POST .../stage/draft
                                             (release the MarketMuse gate)

Both are self-clearing, so nothing loops: intake moves the record to Scoring, and the gate release
moves it to Drafting — neither still matches its own filter afterwards.

It deliberately does NOT touch Needs Attention. That state means a human should look.

Multi-tenant: reads the same Content Production Sites registry as WFP0, so a second site needs a
registry row, not a new workflow.
"""
import json, urllib.request, os

N8N = "https://voyagerscontent.app.n8n.cloud"
PUB = os.environ["N8N_PUB"]
AIRTABLE_CRED = {"id": "mITfEGdTPqCCNrsT", "name": "Airtable API - Weboptimizer"}
REG_BASE = "appPlU9eC5GL6ncjZ"          # ops base
REG_TABLE = "tblOkOXzm2GZUMkYs"         # Content Production Sites
NAME = "WFPD Dispatcher - Content Production (polls Airtable)"
MINUTES = 2

W = "$('Lookup Active Sites').item.json"


def airtable_search(name, formula, pos):
    return {
        "name": name, "type": "n8n-nodes-base.airtable", "typeVersion": 2.1, "position": pos,
        "onError": "continueRegularOutput",
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "id", "value": "={{ %s['Base ID'] }}" % W},
            "table": {"__rl": True, "mode": "id", "value": "={{ %s['Table ID'] }}" % W},
            "filterByFormula": formula,
            "returnAll": True,
            "options": {},
        },
        "credentials": {"airtableTokenApi": AIRTABLE_CRED},
    }


def post_webhook(name, path, pos):
    return {
        "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": pos,
        "onError": "continueRegularOutput",
        "parameters": {
            "method": "POST",
            "url": N8N + "/webhook/galapagos-production/stage/" + path,
            "sendBody": True, "specifyBody": "keypair",
            "bodyParameters": {"parameters": [
                {"name": "site_id", "value": "={{ %s['Site ID'] || %s['Name'] }}" % (W, W)},
                {"name": "record_id", "value": "={{ $json.id }}"},
            ]},
            "options": {},
        },
    }


nodes = [
    {"name": "Every %d minutes" % MINUTES, "type": "n8n-nodes-base.scheduleTrigger",
     "typeVersion": 1.2, "position": [0, 0],
     "parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": MINUTES}]}}},

    {"name": "Lookup Active Sites", "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
     "position": [200, 0],
     "parameters": {
         "operation": "search",
         "base": {"__rl": True, "mode": "id", "value": REG_BASE},
         "table": {"__rl": True, "mode": "id", "value": REG_TABLE},
         "filterByFormula": "={Active} = TRUE()",
         "returnAll": True, "options": {}},
     "credentials": {"airtableTokenApi": AIRTABLE_CRED}},

    # 1 — start anything sitting at Backlog
    airtable_search("Find Backlog", "={Status} = 'Backlog'", [420, -140]),
    post_webhook("Start intake", "intake", [640, -140]),

    # 2 — release hub/pillar pages whose human MarketMuse pass is done
    airtable_search("Find Gate Released",
                    "=AND({Status} = 'Brief Ready', {MarketMuse Score} != '', {Brief Content} != '')",
                    [420, 140]),
    {"name": "Set Drafting", "type": "n8n-nodes-base.airtable", "typeVersion": 2.1,
     "position": [640, 140], "onError": "continueRegularOutput",
     "parameters": {
         "operation": "update",
         "base": {"__rl": True, "mode": "id", "value": "={{ %s['Base ID'] }}" % W},
         "table": {"__rl": True, "mode": "id", "value": "={{ %s['Table ID'] }}" % W},
         "columns": {"mappingMode": "defineBelow", "matchingColumns": ["id"], "schema": [],
                     "value": {"id": "={{ $json.id }}", "Status": "Drafting",
                               "Attempt Count": "={{ 0 }}"}},
         "options": {}},
     "credentials": {"airtableTokenApi": AIRTABLE_CRED}},
    post_webhook("Start draft", "draft", [860, 140]),
]

connections = {
    "Every %d minutes" % MINUTES: {"main": [[{"node": "Lookup Active Sites", "type": "main", "index": 0}]]},
    "Lookup Active Sites": {"main": [[
        {"node": "Find Backlog", "type": "main", "index": 0},
        {"node": "Find Gate Released", "type": "main", "index": 0},
    ]]},
    "Find Backlog": {"main": [[{"node": "Start intake", "type": "main", "index": 0}]]},
    "Find Gate Released": {"main": [[{"node": "Set Drafting", "type": "main", "index": 0}]]},
    "Set Drafting": {"main": [[{"node": "Start draft", "type": "main", "index": 0}]]},
}

body = {"name": NAME, "nodes": nodes, "connections": connections,
        "settings": {"executionOrder": "v1"}}

# create, or update in place if it already exists
req = urllib.request.Request(N8N + "/api/v1/workflows?limit=200",
                             headers={"X-N8N-API-KEY": PUB})
existing = [w for w in json.load(urllib.request.urlopen(req))["data"] if w["name"] == NAME]

if existing:
    wid = existing[0]["id"]
    r = urllib.request.Request(N8N + "/api/v1/workflows/" + wid, data=json.dumps(body).encode(),
                               headers={"X-N8N-API-KEY": PUB, "Content-Type": "application/json"},
                               method="PUT")
    action = "updated"
else:
    r = urllib.request.Request(N8N + "/api/v1/workflows", data=json.dumps(body).encode(),
                               headers={"X-N8N-API-KEY": PUB, "Content-Type": "application/json"},
                               method="POST")
    action = "created"

try:
    wid = json.load(urllib.request.urlopen(r))["id"]
    print("dispatcher %s: %s" % (action, wid))
except urllib.error.HTTPError as e:
    print("ERR %d %s" % (e.code, e.read().decode()[:400])); raise SystemExit(1)

act = urllib.request.Request(N8N + "/api/v1/workflows/%s/activate" % wid, data=b"{}",
                             headers={"X-N8N-API-KEY": PUB, "Content-Type": "application/json"},
                             method="POST")
try:
    print("activated:", json.load(urllib.request.urlopen(act)).get("active"))
except urllib.error.HTTPError as e:
    print("activate ERR %d %s" % (e.code, e.read().decode()[:200]))

open(os.path.join(os.path.dirname(__file__), "WFPD_dispatcher.json"), "w").write(
    json.dumps({"name": NAME, "nodes": nodes, "connections": connections}, indent=2))
print("polls every %d min: Backlog -> intake | Brief Ready + MarketMuse Score -> draft" % MINUTES)
