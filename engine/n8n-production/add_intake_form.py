#!/usr/bin/env python3
"""WFP-Intake-Form: a public n8n hosted form the marketing team uses to queue new pages.

No shell, no Airtable seat needed. On submit it:
  1. creates a "Pages Master" row at Status=Backlog with the page spec, then
  2. fires the WFP0 intake webhook (site_id + the new record_id) so the page runs
     start-to-finish instantly (scoring -> brief -> draft -> ... -> Editor Review).

  New Page Intake (formTrigger) -> Create Page Row (Airtable create) -> Fire Intake (HTTP)

The dispatcher would also pick a Backlog row up within 2h, so even if the instant fire
fails the page is not lost. Idempotent: re-running replaces the workflow by name.

Run:  N8N_API_KEY=... python engine/n8n-production/add_intake_form.py
"""
import json, os, urllib.request, urllib.error

N8N = "https://voyagerscontent.app.n8n.cloud"
BASE_ID = "appNkUL50eF601ejN"
TABLE_ID = "tblUgxSGGfeJIL5GD"
SITE_ID = "galapagosislands-travel-v1"
INTAKE_WEBHOOK = N8N + "/webhook/galapagos-production/stage/intake"
AIRTABLE_CRED = {"airtableTokenApi": {"id": "mITfEGdTPqCCNrsT", "name": "Airtable API - Weboptimizer"}}
WF_NAME = "WFP-Intake Form - GalapagosIslands.travel"
FORM_PATH = "new-page"

PILLARS = ["Cruises", "Wildlife", "Islands", "Itineraries", "Planning", "Activities",
           "Visitor Sites", "FAQ", "Conservation", "Blog"]
PAGE_TYPES = ["Guide", "Hub Page", "Pillar Page", "Final Answer Page", "Blog Post",
              "FAQ Page", "Island Page"]
CTA_BRANDS = ["Voyagers Travel", "Latin Trails"]


def opts(values):
    return {"values": [{"option": v} for v in values]}


def build():
    form = {
        "parameters": {
            "formTitle": "New Page — GalapagosIslands.travel Production",
            "formDescription": "Queue a new page for the content pipeline. Fill this in and submit; "
                               "the page runs itself through scoring, brief, draft, truth-check, humanize, "
                               "polish and audit, then lands in Airtable at <b>Editor Review</b>.",
            "formFields": {"values": [
                {"fieldLabel": "Page Title", "fieldType": "text",
                 "placeholder": "e.g. Best Time to See Whale Sharks in the Galápagos", "requiredField": True},
                {"fieldLabel": "Primary Keyword", "fieldType": "text",
                 "placeholder": "e.g. galapagos whale shark season", "requiredField": True},
                {"fieldLabel": "Pillar", "fieldType": "dropdown", "fieldOptions": opts(PILLARS), "requiredField": True},
                {"fieldLabel": "Page Type", "fieldType": "dropdown", "fieldOptions": opts(PAGE_TYPES), "requiredField": True},
                {"fieldLabel": "Brief / Notes", "fieldType": "textarea",
                 "placeholder": "What should this page cover? Angle, must-include facts, audience, anything the writer needs.",
                 "requiredField": True},
                {"fieldLabel": "Target Word Count", "fieldType": "number",
                 "placeholder": "2500", "requiredField": True},
                {"fieldLabel": "CTA Brand", "fieldType": "dropdown", "fieldOptions": opts(CTA_BRANDS), "requiredField": True},
                {"fieldLabel": "Secondary Keywords", "fieldType": "text",
                 "placeholder": "optional — comma separated", "requiredField": False},
                {"fieldLabel": "Hub Page URL", "fieldType": "text",
                 "placeholder": "optional — the pillar hub this belongs under", "requiredField": False},
                {"fieldLabel": "Named Author", "fieldType": "text",
                 "placeholder": "optional — persona byline, e.g. Juan Magallanes", "requiredField": False},
            ]},
            "responseMode": "onReceived",
            "options": {
                "path": FORM_PATH,
                "buttonLabel": "Queue page for production",
                "appendAttribution": False,
                "ignoreBots": True,
                "respondWithOptions": {"values": {
                    "respondWith": "text",
                    "formSubmittedText": "✅ Your page is queued and now in production. "
                                         "It will appear in Airtable under “Editor Review” when ready "
                                         "(typically ~15–30 minutes). You can submit another page any time.",
                }},
            },
        },
        "id": "form-intake-trigger", "name": "New Page Intake",
        "type": "n8n-nodes-base.formTrigger", "typeVersion": 2.6, "position": [0, 0],
        "webhookId": "galapagos-new-page-form",
    }

    create = {
        "parameters": {
            "operation": "create",
            "base": {"__rl": True, "mode": "id", "value": BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_ID},
            "columns": {"mappingMode": "defineBelow", "value": {
                "Name": "={{ $json['Page Title'] }}",
                "Meta Title": "={{ $json['Page Title'] }}",
                "Primary Keyword": "={{ $json['Primary Keyword'] }}",
                "Pillar": "={{ $json['Pillar'] }}",
                "Page Type": "={{ $json['Page Type'] }}",
                "Topic / Brief": "={{ $json['Brief / Notes'] }}",
                "Suggested Word Count": "={{ $json['Target Word Count'] }}",
                "CTA Brand": "={{ $json['CTA Brand'] }}",
                "Secondary Keywords": "={{ $json['Secondary Keywords'] }}",
                "Hub Page URL": "={{ $json['Hub Page URL'] }}",
                "Named Author": "={{ $json['Named Author'] }}",
                "Status": "Backlog",
            }},
            "options": {"typecast": True},
        },
        "id": "form-create-row", "name": "Create Page Row",
        "type": "n8n-nodes-base.airtable", "typeVersion": 2.1, "position": [260, 0],
        "credentials": AIRTABLE_CRED,
    }

    fire = {
        "parameters": {
            "method": "POST", "url": INTAKE_WEBHOOK, "sendBody": True, "specifyBody": "keypair",
            "bodyParameters": {"parameters": [
                {"name": "site_id", "value": SITE_ID},
                {"name": "record_id", "value": "={{ $json.id }}"},
            ]},
            "options": {},
        },
        "id": "form-fire-intake", "name": "Fire Intake",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [520, 0],
    }

    connections = {
        "New Page Intake": {"main": [[{"node": "Create Page Row", "type": "main", "index": 0}]]},
        "Create Page Row": {"main": [[{"node": "Fire Intake", "type": "main", "index": 0}]]},
    }
    return {"name": WF_NAME, "nodes": [form, create, fire], "connections": connections,
            "settings": {"executionOrder": "v1"}}


def api(path, method="GET", body=None, key=None):
    req = urllib.request.Request(N8N + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-N8N-API-KEY": key, "Content-Type": "application/json"}, method=method)
    return json.load(urllib.request.urlopen(req))


def main():
    wf = build()
    key = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    # save a local copy for the repo
    here = os.path.dirname(__file__)
    json.dump(wf, open(os.path.join(here, "WFP_intake_form.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("built WFP-Intake Form workflow.")
    if not key:
        print("no key — local only."); return
    # find existing by name -> update, else create
    existing = [w for w in api("/api/v1/workflows?limit=100", key=key)["data"] if w["name"] == WF_NAME]
    if existing:
        wid = existing[0]["id"]
        api(f"/api/v1/workflows/{wid}", "PUT", wf, key)
        print("updated existing workflow", wid)
    else:
        d = api("/api/v1/workflows", "POST", wf, key)
        wid = d["id"]
        print("created workflow", wid)
    try:
        api(f"/api/v1/workflows/{wid}/activate", "POST", {}, key)
        print("activated.")
    except urllib.error.HTTPError as e:
        print("activate ERR", e.code, e.read().decode()[:200])
    print("FORM URL (production):", f"{N8N}/form/{FORM_PATH}")


if __name__ == "__main__":
    main()
