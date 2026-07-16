#!/usr/bin/env python3
"""Add a Google Drive export to each CONTENT stage (WFP2/3/5/6), so every artifact
lands as a Google Doc in its ContentEngine stage folder and the record's *Link field
points at the Doc instead of 'airtable://...'.

Only content stages export. WFP4 (truth check) and WFP7 (auditor) are QA gates whose
output is a pass/fail + notes, not a document — those stay in Airtable.

Insertion: Output OK? --true--> [Export to Drive] --> Advance to X --> Trigger next stage
Because the Drive node replaces $json, 'Advance to X' is rewritten to pull the record
and artifact from $('Validate Output') explicitly, and its Link field from the Doc id.
Drive failure is non-fatal (continueRegularOutput): Airtable stays the system of record
and the Link falls back to the airtable:// form.
"""
import json, urllib.request, os

N8N = "https://voyagerscontent.app.n8n.cloud"
PUB = os.environ["N8N_PUB"]
DRIVE_CRED = {"id": "BXOLO4YcNnpHp3SD", "name": "Google Drive account"}

# stage file -> (workflow id, advance node name, content field, link field, folder id, folder label)
STAGES = {
    "WFP2_brief.json":    ("cFY7Tz5q2ih2UCvt", "Advance to Drafting",       "Brief Content",    "Brief Link",
                           "1SF2xCX0_ZLVLtdMV0HCADeeRqnhPuTTh", "03 Page briefs"),
    "WFP3_draft.json":    ("eExgOTVFIoCuJb0D", "Advance to Truth Check",    "Draft Content",    "Draft Link",
                           "1DRmnqM32E40vKB_9JRJNO-yPLD1hl2Nb", "04 First Drafts"),
    "WFP5_humanize.json": ("yh9kMFkbPY34vmVJ", "Advance to Polishing",      "Humanized Content", "Humanized Link",
                           "1IFBQB6v6ht2jS4mNm5RPjMZryf4ro-9Y", "06 Humanized"),
    "WFP6_polish.json":   ("U0MrpTN3hv4RfNMI", "Advance to Auditor Review", "Polished Content", "Polished Link",
                           "1jf8kwaFmFHpYTgmLYSVSMU4yq-YBM5bH", "07 Polished for Editor"),
}

V = "$('Validate Output').item.json"
REC = "$('Re-check and Claim (guarded)').item.json"


def drive_node(label, folder_id):
    return {
        "name": "Export to Drive",
        "type": "n8n-nodes-base.googleDrive",
        "typeVersion": 3,
        "position": [0, 0],
        "onError": "continueRegularOutput",
        "parameters": {
            "resource": "file",
            "operation": "createFromText",
            "content": "={{ %s.artifact }}" % V,
            "name": "={{ (%s['Name'] || %s['Meta Title'] || 'Untitled') + ' — %s' }}" % (REC, REC, label),
            "driveId": {"__rl": True, "mode": "list", "value": "My Drive"},
            "folderId": {"__rl": True, "mode": "id", "value": folder_id},
            "options": {"convertToGoogleDocument": True},
        },
        "credentials": {"googleDriveOAuth2Api": DRIVE_CRED},
    }


def put(wid, wf):
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})}
    r = urllib.request.Request(N8N + "/api/v1/workflows/" + wid, data=json.dumps(body).encode(),
                               headers={"X-N8N-API-KEY": PUB, "Content-Type": "application/json"}, method="PUT")
    try:
        return "ok" if json.load(urllib.request.urlopen(r)).get("id") else "??"
    except urllib.error.HTTPError as e:
        return "ERR %d %s" % (e.code, e.read().decode()[:200])


for fn, (wid, adv, cf, lf, folder, label) in STAGES.items():
    p = os.path.join(os.path.dirname(__file__), fn)
    wf = json.load(open(p))

    wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "Export to Drive"]  # idempotent
    anchor = next(n for n in wf["nodes"] if n["name"] == adv)
    dn = drive_node(label, folder)
    dn["position"] = [anchor["position"][0], anchor["position"][1] - 160]
    wf["nodes"].append(dn)

    # Advance now sits downstream of the Drive node, so $json is the Drive response.
    # Pull record/artifact from Validate explicitly; derive the Link from the Doc id.
    a = anchor["parameters"]
    a["base"]["value"] = "={{ %s.baseId }}" % V
    a["table"]["value"] = "={{ %s.tableId }}" % V
    col = a["columns"]["value"]
    col["id"] = "={{ %s.recordId }}" % V
    col[cf] = "={{ %s.artifact }}" % V
    col[lf] = ("={{ $json.id ? 'https://docs.google.com/document/d/' + $json.id + '/edit'"
               " : 'airtable://%s' }}" % cf)

    # rewire: Output OK? [true] -> Export to Drive -> Advance
    wf["connections"]["Output OK?"]["main"][0] = [{"node": "Export to Drive", "type": "main", "index": 0}]
    wf["connections"]["Export to Drive"] = {"main": [[{"node": adv, "type": "main", "index": 0}]]}

    open(p, "w").write(json.dumps(wf, indent=2))
    print("%-22s -> %-22s (%s)  %s" % (fn, label, folder[:12] + "…", put(wid, wf)))
