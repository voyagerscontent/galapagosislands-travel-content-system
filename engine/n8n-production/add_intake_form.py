#!/usr/bin/env python3
"""WFP-Intake-Form: a public n8n form the marketing team uses to PRODUCE a planned page.

It does NOT create free-text pages. It lets the team pick from the pages already sitting
in the Airtable backlog (Status blank or 'Backlog') and sends the chosen one into
production start-to-finish.

Two-step dynamic form (n8n multi-page form; dynamic dropdown per best-practice = Code
node builds the form JSON):

  Start — Pick Pillar (formTrigger)         page 1: Pillar (+ optional keyword)
    -> List Available Pages (Airtable search)  Status blank/Backlog, that Pillar, title~keyword
    -> Build Page Dropdown (Code)              options = "Title  ·  recID"
    -> Pick the Page (Form, json)             page 2: dynamic Page dropdown + CTA Brand
    -> Resolve Selection (Code)                parse recID out of the chosen option
    -> Queue for Production (Airtable update)  Status=Backlog, CTA Brand, clear stale content
    -> Fire Intake (HTTP)                      WFP0 stage/intake -> full self-chaining run
    -> Done (Form completion)                  confirmation page

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

ANY_PILLAR = "Any pillar (search all)"
PILLARS = [ANY_PILLAR, "Cruises", "Wildlife", "Islands", "Itineraries", "Planning", "Activities",
           "Visitor Sites", "FAQ", "Conservation", "Blog"]
OPTION_CAP = 100  # max pages shown in the page-2 dropdown; keyword narrows below this

# ONLY pages that have NOT been created yet — Status blank/Backlog AND no produced artifacts
# (no Draft/Polished content, not published) — so the form can never re-trigger an already-made
# page (rewrite/optimize is a separate pipeline). Pillar is OPTIONAL: "Any pillar (search all)"
# searches every pillar so the user can just type a title. Keyword is filtered in code (with a
# fallback + cap) so it can never dead-end the form.
LIST_FORMULA = (
    "=AND( OR({Status} = BLANK(), {Status} = 'Backlog'), "
    "{Draft Content} = BLANK(), {Polished Content} = BLANK(), "
    "{Published URL} = BLANK(), {Publish Status} = BLANK(), "
    "OR( '{{ $('Start — Pick Pillar').item.json.Pillar }}' = '" + ANY_PILLAR + "', "
    "{Pillar} = '{{ $('Start — Pick Pillar').item.json.Pillar }}' ) )"
)

BUILD_DROPDOWN_JS = r"""
// Build page-2 dynamically. Keyword filtering happens HERE (not in the Airtable query) so a
// too-narrow keyword can never dead-end the form: if it matches nothing we show all pillar
// pages. Normalize hyphens/spaces so "3 night" matches "3-Night". Encode the record id at the
// end of each option so we can parse it back after submit.
// accent- and punctuation-insensitive: "bartolome" matches "Bartolomé", "3 day" matches "3-Day"
const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
  .toLowerCase().replace(/[-–—_/]/g, ' ').replace(/\s+/g, ' ').trim();
const rows = $input.all().filter(r => r.json && r.json.id);
const kwRaw = String(($('Start — Pick Pillar').first().json['Search by page title']) || '').trim();
const kw = norm(kwRaw);
let matched = rows, note = '';
if (kw) {
  const f = rows.filter(r => norm(r.json['Meta Title']).includes(kw));
  if (f.length) { matched = f; note = ` matching “${kwRaw}”`; }
  else { note = ` — nothing matched “${kwRaw}”, so showing all ${rows.length}`; }
}
const CAP = 100;
let truncated = false;
if (matched.length > CAP) { matched = matched.slice(0, CAP); truncated = true; }
if (truncated) note += ` — showing the first ${CAP}; type part of the title to narrow`;
const options = matched.map(r => `${String(r.json['Meta Title'] || '(untitled)').replace(/\s+/g, ' ').trim()}  ·  ${r.json.id}`);
const pageField = options.length
  ? { fieldLabel: 'Page to produce', fieldType: 'dropdown', requiredField: true, fieldOptions: options }
  : { fieldLabel: 'Page to produce', fieldType: 'dropdown', requiredField: true,
      fieldOptions: ['— no planned pages left in this pillar —'] };
const def = [
  pageField,
  { fieldLabel: 'CTA Brand', fieldType: 'dropdown', requiredField: true,
    fieldOptions: ['Voyagers Travel', 'Latin Trails'] },
];
return [{ json: { formDef: JSON.stringify(def), count: options.length, note } }];
"""

RESOLVE_JS = r"""
const sel = String($json['Page to produce'] || '');
const m = sel.match(/(rec[0-9A-Za-z]{14})\s*$/);
// Guard: the empty-pillar placeholder has no record id — never fire intake on it.
if (!m) throw new Error('No real page was selected. Please reopen the form and choose a page from the list.');
return [{ json: { recordId: m[1], ctaBrand: String($json['CTA Brand'] || ''), selection: sel } }];
"""


def build():
    trigger = {
        "parameters": {
            "formTitle": "Produce a Page — GalapagosIslands.travel",
            "formDescription": "Type part of the page title to find it. Leave the pillar on "
                               "“Any pillar” to search everything, or pick a pillar to narrow. "
                               "Next you'll choose the exact page from a list.",
            "formFields": {"values": [
                {"fieldLabel": "Search by page title", "fieldType": "text",
                 "placeholder": "e.g. honeymoon, 3-day itinerary, Bartolomé", "requiredField": False},
                {"fieldLabel": "Pillar", "fieldType": "dropdown", "defaultValue": ANY_PILLAR,
                 "fieldOptions": {"values": [{"option": p} for p in PILLARS]}, "requiredField": True},
            ]},
            "options": {"path": FORM_PATH, "buttonLabel": "Find pages", "appendAttribution": False, "ignoreBots": True},
        },
        "id": "form-trigger", "name": "Start — Pick Pillar",
        "type": "n8n-nodes-base.formTrigger", "typeVersion": 2.6, "position": [0, 0],
        "webhookId": "galapagos-new-page-form",
    }
    list_pages = {
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "id", "value": BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_ID},
            "filterByFormula": LIST_FORMULA,
            "returnAll": True,
            "options": {},
        },
        "id": "form-list-pages", "name": "List Available Pages",
        "type": "n8n-nodes-base.airtable", "typeVersion": 2.1, "position": [220, 0],
        "credentials": AIRTABLE_CRED, "alwaysOutputData": True,
    }
    build_dd = {
        "parameters": {"jsCode": BUILD_DROPDOWN_JS},
        "id": "form-build-dd", "name": "Build Page Dropdown",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [440, 0],
    }
    pick_page = {
        "parameters": {
            # Reference the Build node BY NAME (not $json): the Form node re-evaluates these
            # expressions when it processes the page-2 submission (resume pass), and on that
            # pass $json is the submission, not the Build output — $json.formDef would be empty
            # ("invalid option 0"). $('Build Page Dropdown').first() resolves on both passes.
            "operation": "page", "defineForm": "json",
            "jsonOutput": "={{ $('Build Page Dropdown').first().json.formDef }}",
            "options": {
                "formTitle": "Choose the page to produce",
                "formDescription": "={{ $('Build Page Dropdown').first().json.count }} planned pages"
                                   "{{ $('Build Page Dropdown').first().json.note }}. Pick one and confirm the CTA brand.",
                "buttonLabel": "Send to production",
            },
        },
        "id": "form-pick-page", "name": "Pick the Page",
        "type": "n8n-nodes-base.form", "typeVersion": 2.5, "position": [660, 0],
    }
    resolve = {
        "parameters": {"jsCode": RESOLVE_JS},
        "id": "form-resolve", "name": "Resolve Selection",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [880, 0],
    }
    queue = {
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "id", "value": BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_ID},
            "columns": {"mappingMode": "defineBelow", "matchingColumns": ["id"], "value": {
                "id": "={{ $json.recordId }}",
                "Status": "Backlog",
                "CTA Brand": "={{ $json.ctaBrand }}",
                "Draft Content": "", "Humanized Content": "", "Polished Content": "",
                "Truth Check Notes": "", "Audit Notes": "", "Last Error": "",
                "Burstiness Retries": "={{ 0 }}", "Attempt Count": "={{ 0 }}",
            }},
            "options": {"typecast": True},
        },
        "id": "form-queue", "name": "Queue for Production",
        "type": "n8n-nodes-base.airtable", "typeVersion": 2.1, "position": [1100, 0],
        "credentials": AIRTABLE_CRED,
    }
    fire = {
        "parameters": {
            "method": "POST", "url": INTAKE_WEBHOOK, "sendBody": True, "specifyBody": "keypair",
            "bodyParameters": {"parameters": [
                {"name": "site_id", "value": SITE_ID},
                {"name": "record_id", "value": "={{ $('Resolve Selection').item.json.recordId }}"},
            ]},
            "options": {},
        },
        "id": "form-fire", "name": "Fire Intake",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1320, 0],
    }
    done = {
        "parameters": {
            "operation": "completion", "respondWith": "text",
            "completionTitle": "✅ Page queued for production",
            "completionMessage": "Your page is now in the pipeline and will appear in Airtable under "
                                 "“Editor Review” when ready (typically ~15–30 minutes). "
                                 "Open the form again to produce another page.",
        },
        "id": "form-done", "name": "Done",
        "type": "n8n-nodes-base.form", "typeVersion": 2.5, "position": [1540, 0],
    }

    order = [trigger, list_pages, build_dd, pick_page, resolve, queue, fire, done]
    connections = {}
    for a, b in zip(order, order[1:]):
        connections[a["name"]] = {"main": [[{"node": b["name"], "type": "main", "index": 0}]]}
    return {"name": WF_NAME, "nodes": order, "connections": connections,
            "settings": {"executionOrder": "v1"}}


def api(path, method="GET", body=None, key=None):
    req = urllib.request.Request(N8N + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-N8N-API-KEY": key, "Content-Type": "application/json"}, method=method)
    return json.load(urllib.request.urlopen(req))


def main():
    wf = build()
    here = os.path.dirname(__file__)
    json.dump(wf, open(os.path.join(here, "WFP_intake_form.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("built WFP-Intake Form (page picker).")
    key = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not key:
        print("no key — local only."); return
    existing = [w for w in api("/api/v1/workflows?limit=100", key=key)["data"] if w["name"] == WF_NAME]
    if existing:
        wid = existing[0]["id"]
        api(f"/api/v1/workflows/{wid}", "PUT", wf, key)
        print("updated workflow", wid)
    else:
        wid = api("/api/v1/workflows", "POST", wf, key)["id"]
        print("created workflow", wid)
    try:
        api(f"/api/v1/workflows/{wid}/activate", "POST", {}, key)
        print("activated.")
    except urllib.error.HTTPError as e:
        print("activate ERR", e.code, e.read().decode()[:200])
    print("FORM URL:", f"{N8N}/form/{FORM_PATH}")


if __name__ == "__main__":
    main()
