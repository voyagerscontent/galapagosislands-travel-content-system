#!/usr/bin/env python3
"""WFP-Intake-Form: public n8n form to PRODUCE a planned (not-yet-created) page, WITH a
confirmation step (search -> review the matched page -> confirm -> produce).

Two form pages, but page 2 is a CONFIRMATION with STATIC fields only (a Yes/No dropdown)
and the record id carried in HIDDEN fields. This avoids the n8n resume bug that a DYNAMIC
page-2 dropdown triggers ("invalid option 0"): on the confirm submit, n8n runs the Form node
in isolation, so we rely only on the submitted hidden values ($json), never on upstream nodes.

  New Page Form (formTrigger)  title + optional pillar + CTA Brand
   -> List Available Pages (Airtable search)   not-created pages (+ pillar if not "Any")
   -> Match (Code)   normalize + rank: exact > starts-with > contains -> one | none | many
   -> Found one? (IF status == 'one')
        true  -> Confirm Page (Form page: shows the title; hidden recordId/ctaBrand/title;
                               static "Yes, produce / No, cancel" dropdown)
              -> Read Confirm (Code, from $json only)
              -> Confirmed? (IF)
                   yes -> Queue for Production -> Fire Intake -> Show Produced (completion)
                   no  -> Show Cancelled (completion)
        false -> Show Retry (completion: none/ambiguous -> refine)

"Not created" = Status blank/Backlog AND no Draft/Polished content, no Published URL/Status.

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
TRIGGER = "New Page Form"

ANY_PILLAR = "Any pillar (search all)"
PILLARS = [ANY_PILLAR, "Cruises", "Wildlife", "Islands", "Itineraries", "Planning", "Activities",
           "Visitor Sites", "FAQ", "Conservation", "Blog"]

LIST_FORMULA = (
    "=AND( OR({Status} = BLANK(), {Status} = 'Backlog'), "
    "{Draft Content} = BLANK(), {Polished Content} = BLANK(), "
    "{Published URL} = BLANK(), {Publish Status} = BLANK(), "
    "OR( '{{ $('" + TRIGGER + "').item.json.Pillar }}' = '" + ANY_PILLAR + "', "
    "{Pillar} = '{{ $('" + TRIGGER + "').item.json.Pillar }}' ) )"
)

MATCH_JS = r"""
const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
  .toLowerCase().replace(/[-–—_/]/g, ' ').replace(/\s+/g, ' ').trim();
const trig = $('__TRIGGER__').first().json;
const kwRaw = String(trig['Page title'] || '').trim();
const cta = String(trig['CTA Brand'] || '');
const kw = norm(kwRaw);
const rows = $input.all().filter(r => r.json && r.json.id)
  .map(r => ({ id: r.json.id, title: String(r.json['Meta Title'] || '(untitled)').replace(/\s+/g,' ').trim() }));
rows.forEach(r => r.n = norm(r.title));
if (!kw) return [{ json: { status: 'none', retryMsg: 'Please type part of the page title, then submit again.' } }];
const exact = rows.filter(r => r.n === kw);
const starts = rows.filter(r => r.n.startsWith(kw));
const contains = rows.filter(r => r.n.includes(kw));
let pick = null, pool = null;
if (exact.length === 1) pick = exact[0];
else if (exact.length > 1) pool = exact;
else if (starts.length === 1) pick = starts[0];
else if (contains.length === 1) pick = contains[0];
else pool = contains;
if (pick) return [{ json: { status: 'one', recordId: pick.id, title: pick.title, ctaBrand: cta } }];
// none / ambiguous -> render a CLICKABLE list. Each match links back to the form pre-filled
// with that EXACT title (n8n prefills fields from query params), so one click -> exact match
// -> confirm -> produce, instead of retyping.
const esc = t => String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const enc = encodeURIComponent;
const link = t => 'https://voyagerscontent.app.n8n.cloud/form/new-page?Page%20title=' + enc(t)
  + '&Pillar=' + enc('__ANY__') + '&CTA%20Brand=' + enc(cta || 'Voyagers Travel');
if (!pool || pool.length === 0)
  return [{ json: { status: 'none', retryHtml: `<div style="font-size:15px;line-height:1.5"><p>No planned page matched “${esc(kwRaw)}”.</p><p>Go back and try different or fewer words. (Already-published pages are handled by the separate optimize pipeline.)</p></div>` } }];
const items = pool.slice(0, 40).map(r => `<li style="margin:7px 0"><a href="${link(r.title)}">${esc(r.title)}</a></li>`).join('');
const more = pool.length > 40 ? `<p>…and ${pool.length - 40} more — type more of the title to narrow.</p>` : '';
return [{ json: { status: 'many', retryHtml: `<div style="font-size:15px;line-height:1.5"><p><b>${pool.length}</b> planned pages match “${esc(kwRaw)}”. Click the exact page you want to produce:</p><ul>${items}</ul>${more}</div>` } }];
""".replace("__TRIGGER__", TRIGGER).replace("__ANY__", ANY_PILLAR)

READ_CONFIRM_JS = r"""
// Resume pass — use ONLY the submitted hidden fields + the confirm choice ($json), never upstream.
const j = $json;
return [{ json: {
  recordId: String(j.recordId || ''), ctaBrand: String(j.ctaBrand || ''),
  pageTitle: String(j.pageTitle || ''), confirm: String(j.Confirm || ''),
} }];
"""


def build():
    trigger = {
        "parameters": {
            "formTitle": "Produce a Page — GalapagosIslands.travel",
            "formDescription": "Type part of the page title to find a planned page. Leave the pillar on "
                               "“Any pillar” to search everything. You'll review and confirm before it's produced.",
            "formFields": {"values": [
                {"fieldLabel": "Page title", "fieldType": "text",
                 "placeholder": "e.g. 3-day itinerary, honeymoon cruise, Bartolomé", "requiredField": True},
                {"fieldLabel": "Pillar", "fieldType": "dropdown", "defaultValue": ANY_PILLAR,
                 "fieldOptions": {"values": [{"option": p} for p in PILLARS]}, "requiredField": True},
                {"fieldLabel": "CTA Brand", "fieldType": "dropdown", "requiredField": True,
                 "fieldOptions": {"values": [{"option": "Voyagers Travel"}, {"option": "Latin Trails"}]}},
            ]},
            "options": {"path": FORM_PATH, "buttonLabel": "Find page", "appendAttribution": False, "ignoreBots": True},
        },
        "id": "form-trigger", "name": TRIGGER,
        "type": "n8n-nodes-base.formTrigger", "typeVersion": 2.6, "position": [0, 0],
        "webhookId": "galapagos-new-page-form",
    }
    list_pages = {
        "parameters": {
            "operation": "search",
            "base": {"__rl": True, "mode": "id", "value": BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_ID},
            "filterByFormula": LIST_FORMULA, "returnAll": True, "options": {},
        },
        "id": "form-list", "name": "List Available Pages",
        "type": "n8n-nodes-base.airtable", "typeVersion": 2.1, "position": [220, 0],
        "credentials": AIRTABLE_CRED, "alwaysOutputData": True,
    }
    match = {"parameters": {"jsCode": MATCH_JS}, "id": "form-match", "name": "Match",
             "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [440, 0]}
    found = {"parameters": {"conditions": {"string": [{"value1": "={{ $json.status }}", "value2": "one"}]}},
             "id": "form-found", "name": "Found one?",
             "type": "n8n-nodes-base.if", "typeVersion": 1, "position": [640, 0]}
    confirm_page = {
        "parameters": {
            "operation": "page", "defineForm": "fields",
            "formFields": {"values": [
                {"fieldType": "html",
                 "html": "=<div style=\"font-size:15px;line-height:1.5\"><p>You're about to send this page into "
                         "production:</p><p style=\"font-size:18px\"><b>{{ $('Match').first().json.title }}</b></p>"
                         "<p>CTA brand: <b>{{ $('Match').first().json.ctaBrand }}</b></p>"
                         "<p>Confirm below to produce it, or choose “No” to cancel.</p></div>"},
                {"fieldType": "hiddenField", "fieldName": "recordId",
                 "fieldValue": "={{ $('Match').first().json.recordId }}"},
                {"fieldType": "hiddenField", "fieldName": "ctaBrand",
                 "fieldValue": "={{ $('Match').first().json.ctaBrand }}"},
                {"fieldType": "hiddenField", "fieldName": "pageTitle",
                 "fieldValue": "={{ $('Match').first().json.title }}"},
                {"fieldLabel": "Confirm", "fieldType": "dropdown", "requiredField": True,
                 "fieldOptions": {"values": [{"option": "Yes, produce this page"}, {"option": "No, cancel"}]}},
            ]},
            "options": {"formTitle": "Confirm the page", "buttonLabel": "Continue"},
        },
        "id": "form-confirm", "name": "Confirm Page",
        "type": "n8n-nodes-base.form", "typeVersion": 2.5, "position": [860, -120],
    }
    read_confirm = {"parameters": {"jsCode": READ_CONFIRM_JS}, "id": "form-read", "name": "Read Confirm",
                    "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1080, -120]}
    confirmed = {"parameters": {"conditions": {"string": [
        {"value1": "={{ $json.confirm }}", "operation": "contains", "value2": "Yes"}]}},
        "id": "form-confirmed", "name": "Confirmed?",
        "type": "n8n-nodes-base.if", "typeVersion": 1, "position": [1280, -120]}
    queue = {
        "parameters": {
            "operation": "update",
            "base": {"__rl": True, "mode": "id", "value": BASE_ID},
            "table": {"__rl": True, "mode": "id", "value": TABLE_ID},
            "columns": {"mappingMode": "defineBelow", "matchingColumns": ["id"], "value": {
                "id": "={{ $json.recordId }}",
                "Status": "Backlog", "CTA Brand": "={{ $json.ctaBrand }}",
                "Draft Content": "", "Humanized Content": "", "Polished Content": "",
                "Truth Check Notes": "", "Audit Notes": "", "Last Error": "",
                "Burstiness Retries": "={{ 0 }}", "Attempt Count": "={{ 0 }}",
            }}, "options": {"typecast": True},
        },
        "id": "form-queue", "name": "Queue for Production",
        "type": "n8n-nodes-base.airtable", "typeVersion": 2.1, "position": [1500, -220],
        "credentials": AIRTABLE_CRED,
    }
    fire = {
        "parameters": {
            "method": "POST", "url": INTAKE_WEBHOOK, "sendBody": True, "specifyBody": "keypair",
            "bodyParameters": {"parameters": [
                {"name": "site_id", "value": SITE_ID},
                {"name": "record_id", "value": "={{ $('Read Confirm').first().json.recordId }}"},
            ]}, "options": {},
        },
        "id": "form-fire", "name": "Fire Intake",
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1720, -220],
    }
    produced = {
        "parameters": {
            "operation": "completion", "respondWith": "text",
            "completionTitle": "✅ Page queued for production",
            "completionMessage": "=Producing “{{ $('Read Confirm').first().json.pageTitle }}”. It will appear in "
                                 "Airtable under “Editor Review” when ready (~15–30 minutes). Reopen the form to produce another.",
        },
        "id": "form-produced", "name": "Show Produced",
        "type": "n8n-nodes-base.form", "typeVersion": 2.5, "position": [1940, -220],
    }
    cancelled = {
        "parameters": {
            "operation": "completion", "respondWith": "text",
            "completionTitle": "Cancelled",
            "completionMessage": "Nothing was produced. Reopen the form to search again.",
        },
        "id": "form-cancelled", "name": "Show Cancelled",
        "type": "n8n-nodes-base.form", "typeVersion": 2.5, "position": [1500, 40],
    }
    retry = {
        "parameters": {
            "operation": "completion", "respondWith": "showText",
            "responseText": "={{ $('Match').first().json.retryHtml }}",
        },
        "id": "form-retry", "name": "Show Retry",
        "type": "n8n-nodes-base.form", "typeVersion": 2.5, "position": [860, 140],
    }

    nodes = [trigger, list_pages, match, found, confirm_page, read_confirm, confirmed,
             queue, fire, produced, cancelled, retry]
    C = {
        TRIGGER: {"main": [[{"node": "List Available Pages", "type": "main", "index": 0}]]},
        "List Available Pages": {"main": [[{"node": "Match", "type": "main", "index": 0}]]},
        "Match": {"main": [[{"node": "Found one?", "type": "main", "index": 0}]]},
        "Found one?": {"main": [
            [{"node": "Confirm Page", "type": "main", "index": 0}],   # true
            [{"node": "Show Retry", "type": "main", "index": 0}],     # false
        ]},
        "Confirm Page": {"main": [[{"node": "Read Confirm", "type": "main", "index": 0}]]},
        "Read Confirm": {"main": [[{"node": "Confirmed?", "type": "main", "index": 0}]]},
        "Confirmed?": {"main": [
            [{"node": "Queue for Production", "type": "main", "index": 0}],  # true
            [{"node": "Show Cancelled", "type": "main", "index": 0}],        # false
        ]},
        "Queue for Production": {"main": [[{"node": "Fire Intake", "type": "main", "index": 0}]]},
        "Fire Intake": {"main": [[{"node": "Show Produced", "type": "main", "index": 0}]]},
    }
    return {"name": WF_NAME, "nodes": nodes, "connections": C, "settings": {"executionOrder": "v1"}}


def api(path, method="GET", body=None, key=None):
    req = urllib.request.Request(N8N + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-N8N-API-KEY": key, "Content-Type": "application/json"}, method=method)
    return json.load(urllib.request.urlopen(req))


def main():
    wf = build()
    here = os.path.dirname(__file__)
    json.dump(wf, open(os.path.join(here, "WFP_intake_form.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("built WFP-Intake Form (search + confirm + produce).")
    key = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not key:
        print("no key — local only."); return
    existing = [w for w in api("/api/v1/workflows?limit=100", key=key)["data"] if w["name"] == WF_NAME]
    wid = existing[0]["id"] if existing else None
    if wid:
        api(f"/api/v1/workflows/{wid}", "PUT", wf, key); print("updated workflow", wid)
    else:
        wid = api("/api/v1/workflows", "POST", wf, key)["id"]; print("created workflow", wid)
    try:
        api(f"/api/v1/workflows/{wid}/activate", "POST", {}, key); print("activated.")
    except urllib.error.HTTPError as e:
        print("activate ERR", e.code, e.read().decode()[:200])
    print("FORM URL:", f"{N8N}/form/{FORM_PATH}")


if __name__ == "__main__":
    main()
