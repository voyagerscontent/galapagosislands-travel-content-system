#!/usr/bin/env python3
"""WFP0: clear every downstream field on intake, so setting Status=Backlog ALWAYS re-runs clean.

Without this, a second run silently stalls. Each stage claim-guards on its own output field
being empty (WFP1 guards `{ROI Score} = ''`, WFP2 `{Brief Content} = ''`, ...). After one run
those fields are populated, so a re-run's guard matches nothing — and the stage does not halt
cleanly: Airtable returns one empty item, the agent is prompted with no record and replies
"I'm ready", the validator fails with an empty recordId, and the error route then 422s trying
to update a record with no id. The user sees a record stuck at Scoring with no explanation.

Intake is the only place that knows a fresh run is starting, so it owns the reset. This makes
the whole chain idempotent and is what lets an Airtable automation drive it: change the cell,
the pipeline runs, end to end, every time — no manual field clearing.
"""
import json, urllib.request, os

N8N = "https://voyagerscontent.app.n8n.cloud"
PUB = os.environ["N8N_PUB"]
WID = "i8xtkx9GBw1aRdkP"
FN = "WFP0_production_intake.json"

# number fields must be cleared with null, not '' (Airtable 422s on '' for a number)
# MarketMuse Score is cleared too: a rebuilt brief deserves a fresh MarketMuse pass, and leaving a
# stale score would let the dispatcher auto-release a Backlog re-run past the gate.
NUM = ["ROI Score", "Buyer Intent (1-5)", "Search Demand (1-5)", "Ranking Chance (1-5)",
       "Conversion Value (1-5)", "MarketMuse Score"]
TXT = ["Brief Content", "Draft Content", "Humanized Content", "Polished Content",
       "Conversion Review", "Truth Check Notes", "Audit Notes",
       "Brief Link", "Draft Link", "Humanized Link", "Polished Link",
       "Target Keywords (NW/MM)", "Last Error", "Return To"]

p = os.path.join(os.path.dirname(__file__), FN)
wf = json.load(open(p))

adv = next(n for n in wf["nodes"] if n["name"] == "Advance to Scoring")
col = adv["parameters"]["columns"]["value"]
for f in NUM:
    col[f] = "={{ null }}"
for f in TXT:
    col[f] = ""

body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
        "settings": wf.get("settings", {"executionOrder": "v1"})}
r = urllib.request.Request(N8N + "/api/v1/workflows/" + WID, data=json.dumps(body).encode(),
                           headers={"X-N8N-API-KEY": PUB, "Content-Type": "application/json"},
                           method="PUT")
try:
    ok = "ok" if json.load(urllib.request.urlopen(r)).get("id") else "??"
except urllib.error.HTTPError as e:
    ok = "ERR %d %s" % (e.code, e.read().decode()[:200])

open(p, "w").write(json.dumps(wf, indent=2))
print("WFP0 intake now resets %d numeric + %d text fields on claim -> %s" % (len(NUM), len(TXT), ok))
