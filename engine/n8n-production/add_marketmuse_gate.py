#!/usr/bin/env python3
"""WFP2: hold Hub/Pillar pages at Brief Ready until a human has run MarketMuse.

Hub and Pillar are commercial category pages where topical coverage decides whether the page
ranks; they get a human topic-model pass before anything is drafted. Guides, FAQs, wildlife,
island and blog pages chain straight through — gating them would add a manual step for no gain.

No new Status is introduced: the 12-state contract is shared byte-for-byte with Airtable, every
n8n filter, the orchestrator and the auditor (engine/CLAUDE.md, "The one rule"). The gate works
by *withholding the advance* instead — the record keeps Status = Brief Ready, its brief written,
and nothing chains. It cannot re-fire while it waits because WFP2's own claim guard requires
{Brief Content} = '', which is now filled.

    Output OK? -> Export to Drive -> MarketMuse gate?
                                       ├─ true  -> Hold for MarketMuse   (Status stays Brief Ready, no chain)
                                       └─ false -> Advance to Drafting -> Trigger next stage

'MarketMuse Score' is the gate field: filling it releases the page (Airtable automation #2 sets
Status=Drafting and POSTs the draft webhook). Score 0 = an explicit decision to skip.
"""
import json, urllib.request, os, copy

N8N = "https://voyagerscontent.app.n8n.cloud"
PUB = os.environ["N8N_PUB"]
WID = "cFY7Tz5q2ih2UCvt"
FN = "WFP2_brief.json"
ADV = "Advance to Drafting"
GATED_TYPES = ["Hub Page", "Pillar Page"]

REC = "$('Re-check and Claim (guarded)').item.json"
GATE_EXPR = ("={{ %s.includes($('Re-check and Claim (guarded)').item.json['Page Type']) "
             "&& !$('Re-check and Claim (guarded)').item.json['MarketMuse Score'] }}"
             % json.dumps(GATED_TYPES))

p = os.path.join(os.path.dirname(__file__), FN)
wf = json.load(open(p))

NEW = ["MarketMuse gate?", "Hold for MarketMuse"]
wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in NEW]
for k in NEW:
    wf["connections"].pop(k, None)

adv = next(n for n in wf["nodes"] if n["name"] == ADV)
x, y = adv["position"]

# Hold = the advance, but Status stays Brief Ready. Same artifact/link writes, so the brief and
# its Doc are saved and the editor can read it while MarketMuse runs.
hold = copy.deepcopy(adv)
hold["name"] = "Hold for MarketMuse"
hold["position"] = [x, y + 190]
hold["parameters"]["columns"]["value"]["Status"] = "Brief Ready"

wf["nodes"].append({
    "name": "MarketMuse gate?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": [x - 190, y],
    "parameters": {"conditions": {"options": {"caseSensitive": True, "version": 2},
                                  "combinator": "and",
                                  "conditions": [{"operator": {"type": "boolean", "operation": "true", "singleValue": True},
                                                  "leftValue": GATE_EXPR,
                                                  "rightValue": ""}]},
                   "options": {}},
})
wf["nodes"].append(hold)

# Export to Drive currently feeds the advance; route it through the gate instead.
wf["connections"]["Export to Drive"] = {"main": [[{"node": "MarketMuse gate?", "type": "main", "index": 0}]]}
wf["connections"]["MarketMuse gate?"] = {"main": [
    [{"node": "Hold for MarketMuse", "type": "main", "index": 0}],   # gated: stop here
    [{"node": ADV, "type": "main", "index": 0}],                     # not gated: carry on
]}
# Hold deliberately has NO outgoing connection — the chain stops until a human releases it.

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
print("WFP2 gate: %s hold at Brief Ready until MarketMuse Score is filled -> %s"
      % ("/".join(GATED_TYPES), ok))
