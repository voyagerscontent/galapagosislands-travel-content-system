#!/usr/bin/env python3
"""Build WFP1..WFP7 production stage workflows in n8n (inactive) + save JSON to repo.
Pattern (from live WF3): webhook -> registry lookup -> claim-guard -> Anthropic ->
validate(JSON) -> advance | Needs Attention. Artifacts stored in Airtable long-text
fields (airtable:// links), matching the proven Weboptimizer pattern. Idempotent-ish:
re-running creates NEW workflows (delete olds first if re-building).
"""
import json, urllib.request, os

N8N = "https://voyagerscontent.app.n8n.cloud"
PUB = os.environ["N8N_PUB"]
OPS_BASE, REG_TABLE = "appPlU9eC5GL6ncjZ", "tblOkOXzm2GZUMkYs"
AT_CRED = {"airtableTokenApi": {"id": "mITfEGdTPqCCNrsT", "name": "Airtable API - Weboptimizer"}}
ANTHROPIC_CRED = {"anthropicApi": {"id": "fQbptY6CtcIWVwYp", "name": "Anthropic - Weboptimizer"}}
OPUS, HAIKU = "claude-opus-4-8", "claude-haiku-4-5-20251001"

LAW = (
"CONTEXT — obey verbatim.\n"
"BRAND: Galapagos Islands.Travel (galapagosislands.travel), an INDEPENDENT editorial guide. "
"Never 'Galapagos Travel Center'; domain is never galapagosislands.com. Author: Juan Magallanes; "
"contributors only from the approved pool (e.g. Andre Robles / Voyagers Travel Company, Luisa Cordova / Golden Galapagos).\n"
"HARD TRUTHS (never violate): (HT-1) The Galapagos is great year-round; never call a time 'best/worst' "
"without stating what species/event it is for; one species is not the whole destination. "
"(HT-2) No island is 'better'; luxury = the yacht experience, not which islands a boat visits; every island "
"is reachable on a 5-day-or-longer cruise; only Fernandina and west Isabela need more than 4 days; the shortest "
"cruise is 4 days and can be luxury.\n"
"VOICE: honest, plain-spoken, answer-first, one idea per sentence, no padding. "
"BANNED words: #1, best, world-class, paradise, hidden gem, luxury-as-filler, unforgettable, must-see, dream vacation. "
"No fabricated numbers — every figure must be sourced or marked [VERIFY]. One primary CTA: "
"'Talk to a Galapagos Specialist' (a lead, never 'Book Now'). No operator favoritism.\n"
"OUTPUT: return ONLY the STRICT JSON object described — no prose, no code fences.\n\n"
)

REC = "{{ $json['Meta Title'] }} | brief: {{ $json['Topic / Brief'] }} | pillar: {{ $json['Pillar'] }} | page type: {{ $json['Page Type'] }}"

def prompt(task, body=""):
    return "=" + LAW + task + "\n\nRECORD: " + REC + ("\n\n" + body if body else "")

STAGES = [
 dict(n=1, slug="scoring", status="Scoring", nxt="Brief Ready", model=HAIKU, guard="{ROI Score} = ''", kind="score",
   task="TASK — Score this page topic for editorial ROI (1-5 each). roi_score = buyer_intent*conversion_value + search_demand*ranking_chance. "
        "Return STRICT JSON {\"buyer_intent\":n,\"search_demand\":n,\"ranking_chance\":n,\"conversion_value\":n,\"roi_score\":n,\"rationale\":\"...\"}."),
 dict(n=2, slug="brief", status="Brief Ready", nxt="Drafting", model=OPUS, guard="{Brief Content} = ''", kind="content", key="brief_markdown", cf="Brief Content", lf="Brief Link",
   task="TASK — Produce the content brief. Include: exact target query, persona + funnel stage, section outline (one H1, H2/H3 tree), the 40-60 word answer-box target, 6-10 FAQ questions (People-Also-Ask style), required schema (Article+FAQPage+BreadcrumbList for a guide), and the facts to ground with their sources. Follow the page-type template (GUIDE_PAGE_SPEC for guides). Return STRICT JSON {\"brief_markdown\":\"...\"}."),
 dict(n=3, slug="draft", status="Drafting", nxt="Truth Check", model=OPUS, guard="{Draft Content} = ''", kind="content", key="draft_markdown", cf="Draft Content", lf="Draft Link",
   task="TASK — Write the full page draft from the brief, obeying LAW and the page template. Include a meta title (50-60 chars) and meta description (140-160), one H1, clean H2/H3, an answer box (40-60 words), at least one data table where useful, a 6-10 question FAQ with 40-60 word answers, and one CTA. Every figure sourced or [VERIFY]. Return STRICT JSON {\"draft_markdown\":\"...\"}.",
   body="BRIEF: {{ $json['Brief Content'] }}"),
 dict(n=4, slug="truthcheck", status="Truth Check", nxt="Humanizing", model=OPUS, guard="{Truth Check Notes} = ''", kind="qa", nf="Truth Check Notes",
   task="TASK — Truth-check the draft. Every factual claim must be sourced/traceable or marked [VERIFY]; no invented numbers; HARD TRUTHS honored; brand/entity rules met. Return STRICT JSON {\"pass\":true|false,\"notes\":\"per-claim findings\"}.",
   body="DRAFT: {{ $json['Draft Content'] }}"),
 dict(n=5, slug="humanize", status="Humanizing", nxt="Polishing", model=OPUS, guard="{Humanized Content} = ''", kind="content", key="humanized_markdown", cf="Humanized Content", lf="Humanized Link",
   task="TASK — Rewrite for natural human cadence WITHOUT changing facts, numbers, sources, [VERIFY] flags, or structure. Keep answer-first and in brand voice; no banned words. Return STRICT JSON {\"humanized_markdown\":\"...\"}.",
   body="DRAFT: {{ $json['Draft Content'] }}"),
 dict(n=6, slug="polish", status="Polishing", nxt="Auditor Review", model=OPUS, guard="{Polished Content} = ''", kind="content", key="polished_html", cf="Polished Content", lf="Polished Link",
   task="TASK — Final polish and assemble the production build. Emit the final page as HTML implementing the page template: meta title/description, semantic H1/H2/H3, answer box, a data table where useful, FAQ accordion, related links, one CTA, and JSON-LD (Article + FAQPage + BreadcrumbList; FAQ schema must byte-match the visible FAQ). Return STRICT JSON {\"polished_html\":\"...\"}.",
   body="HUMANIZED: {{ $json['Humanized Content'] }}"),
 dict(n=7, slug="auditor", status="Auditor Review", nxt="Editor Review", model=OPUS, guard="{Audit Notes} = ''", kind="qa", nf="Audit Notes",
   task="TASK — Run the full auditor checklist: A Truth (sourced), B Entity rules, C Brand voice (no banned words), D Audience+one CTA, E Page-type structure + schema present and mirroring visible content, F Content fidelity (no padding, answer-first, scannable), G Conversion safety. Return STRICT JSON {\"pass\":true|false,\"notes\":\"per-part PASS/FAIL findings\"}.",
   body="PAGE: {{ $json['Polished Content'] }}"),
]

def at_search(name, base, table, formula, pos, always=False):
    node = {"parameters": {"operation": "search", "base": {"__rl": True, "mode": "id", "value": base},
            "table": {"__rl": True, "mode": "id", "value": table}, "filterByFormula": formula,
            "returnAll": False, "limit": 1, "options": {}},
            "name": name, "type": "n8n-nodes-base.airtable", "typeVersion": 2.1, "position": pos, "credentials": AT_CRED}
    if always: node["alwaysOutputData"] = True
    return node

def at_update(name, value_map, pos):
    return {"parameters": {"operation": "update", "base": {"__rl": True, "mode": "id", "value": "={{ $json.baseId }}"},
            "table": {"__rl": True, "mode": "id", "value": "={{ $json.tableId }}"},
            "columns": {"mappingMode": "defineBelow", "value": value_map, "matchingColumns": ["id"], "schema": []},
            "options": {}},
            "name": name, "type": "n8n-nodes-base.airtable", "typeVersion": 2.1, "position": pos, "credentials": AT_CRED}

def anthropic(name, model, ptext, pos):
    return {"parameters": {"modelId": {"__rl": True, "mode": "id", "value": model},
            "messages": {"values": [{"content": ptext}]}, "options": {"maxTokens": 16000}},
            "name": name, "type": "@n8n/n8n-nodes-langchain.anthropic", "typeVersion": 1, "position": pos, "credentials": ANTHROPIC_CRED}

VHEAD = ("const rec = $items('Re-check and Claim (guarded)')[0] ? $items('Re-check and Claim (guarded)')[0].json : {};\n"
"const site = $items('Lookup Site (registry)')[0] ? $items('Lookup Site (registry)')[0].json : {};\n"
"let raw = Array.isArray($json.content) ? $json.content.filter(b=>b.type==='text').map(b=>b.text).join('') : ($json.message && $json.message.content ? $json.message.content : ($json.text||''));\n"
"raw=(raw||'').trim();\n"
"if(raw.startsWith('```')){const f=raw.match(/^```(?:json)?\\s*([\\s\\S]*?)```\\s*$/);if(f)raw=f[1].trim();}\n"
"const _s0=raw.indexOf('{'),_e0=raw.lastIndexOf('}'); if(_s0!==-1&&_e0>_s0) raw=raw.slice(_s0,_e0+1);\n"
"let _o='',_in=false,_esc=false;\n"
"for(const c of raw){ if(_in){ if(_esc){_o+=c;_esc=false;continue;} if(c==='\\\\'){_o+=c;_esc=true;continue;} if(c==='\"'){_in=false;_o+=c;continue;} if(c==='\\n'){_o+='\\\\n';continue;} if(c==='\\r'){_o+='\\\\r';continue;} if(c==='\\t'){_o+='\\\\t';continue;} _o+=c;continue;} if(c==='\"')_in=true; _o+=c; }\n"
"raw=_o;\n"
"const rid=rec.id||'', bid=site['Base ID']||'', tid=site['Table ID']||'';\n")

def validator(stage):
    k = stage["kind"]
    if k == "content":
        body = (VHEAD +
        "let out={recordId:rid,baseId:bid,tableId:tid,ok:false,error:'',artifact:''};\n"
        "try{ const p=JSON.parse(raw); const a=p['%s']; if(typeof a==='string'&&a.length>40){out.artifact=a;out.ok=true;} else out.error='Missing/short %s';}catch(e){out.error='Unparseable LLM output: '+e.message;}\n"
        "return [{json:out}];" % (stage["key"], stage["key"]))
    elif k == "score":
        body = (VHEAD +
        "let out={recordId:rid,baseId:bid,tableId:tid,ok:false,error:'',buyer_intent:0,search_demand:0,ranking_chance:0,conversion_value:0,roi_score:0};\n"
        "try{ const p=JSON.parse(raw); out.buyer_intent=Number(p.buyer_intent)||0; out.search_demand=Number(p.search_demand)||0; out.ranking_chance=Number(p.ranking_chance)||0; out.conversion_value=Number(p.conversion_value)||0; out.roi_score=Number(p.roi_score)||(out.buyer_intent*out.conversion_value+out.search_demand*out.ranking_chance); out.ok=out.buyer_intent>0; if(!out.ok)out.error='Missing scores';}catch(e){out.error='Unparseable LLM output: '+e.message;}\n"
        "return [{json:out}];")
    else:  # qa
        body = (VHEAD +
        "let out={recordId:rid,baseId:bid,tableId:tid,ok:false,error:'',notes:''};\n"
        "try{ const p=JSON.parse(raw); out.notes=String(p.notes||''); const pass=(p.pass===true||p.pass==='true'); out.ok=pass; if(!pass)out.error='QA FAIL: '+out.notes;}catch(e){out.error='Unparseable LLM output: '+e.message;}\n"
        "return [{json:out}];")
    return body

def advance_map(stage):
    base = {"id": "={{ $json.recordId }}", "Status": stage["nxt"], "Attempt Count": "={{ 0 }}"}
    if stage["kind"] == "content":
        base[stage["cf"]] = "={{ $json.artifact }}"
        base[stage["lf"]] = "airtable://" + stage["cf"]
    elif stage["kind"] == "score":
        base.update({"Buyer Intent (1-5)": "={{ $json.buyer_intent }}", "Search Demand (1-5)": "={{ $json.search_demand }}",
                     "Ranking Chance (1-5)": "={{ $json.ranking_chance }}", "Conversion Value (1-5)": "={{ $json.conversion_value }}",
                     "ROI Score": "={{ $json.roi_score }}"})
    else:
        base[stage["nf"]] = "={{ $json.notes }}"
    return base

def build(stage):
    wh = {"parameters": {"path": "galapagos-production/stage/" + stage["slug"], "httpMethod": "POST", "responseMode": "onReceived", "options": {}},
          "name": "Airtable Status Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 1, "position": [220, 300],
          "webhookId": "gal-prod-" + stage["slug"]}
    lookup = at_search("Lookup Site (registry)", OPS_BASE, REG_TABLE, "=AND({Site ID} = '{{ $json.body.site_id }}', {Active} = 1)", [420, 300])
    claim = at_search("Re-check and Claim (guarded)", "={{ $json['Base ID'] }}", "={{ $json['Table ID'] }}",
        "=AND({Status} = '%s', %s, RECORD_ID() = '{{ $('Airtable Status Webhook').item.json.body.record_id }}')" % (stage["status"], stage["guard"]),
        [620, 300], always=True)
    ptext = prompt(stage["task"], stage.get("body", ""))
    ai = anthropic("Run Stage Agent", stage["model"], ptext, [820, 300])
    val = {"parameters": {"jsCode": validator(stage)}, "name": "Validate Output", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1020, 300]}
    iff = {"parameters": {"conditions": {"boolean": [{"value1": "={{ $json.ok }}", "value2": True}]}},
           "name": "Output OK?", "type": "n8n-nodes-base.if", "typeVersion": 1, "position": [1220, 300]}
    adv = at_update("Advance to " + stage["nxt"], advance_map(stage), [1440, 220])
    na = at_update("Route to Needs Attention", {"id": "={{ $json.recordId }}", "Status": "Needs Attention",
          "Last Error": "={{ $json.error }}", "Return To": stage["status"]}, [1440, 400])
    nodes = [wh, lookup, claim, ai, val, iff, adv, na]
    conns = {
      "Airtable Status Webhook": {"main": [[{"node": "Lookup Site (registry)", "type": "main", "index": 0}]]},
      "Lookup Site (registry)": {"main": [[{"node": "Re-check and Claim (guarded)", "type": "main", "index": 0}]]},
      "Re-check and Claim (guarded)": {"main": [[{"node": "Run Stage Agent", "type": "main", "index": 0}]]},
      "Run Stage Agent": {"main": [[{"node": "Validate Output", "type": "main", "index": 0}]]},
      "Validate Output": {"main": [[{"node": "Output OK?", "type": "main", "index": 0}]]},
      "Output OK?": {"main": [[{"node": "Advance to " + stage["nxt"], "type": "main", "index": 0}], [{"node": "Route to Needs Attention", "type": "main", "index": 0}]]},
    }
    name = "WFP%d %s - GalapagosIslands.travel" % (stage["n"], stage["status"])
    return {"name": name, "nodes": nodes, "connections": conns, "settings": {"executionOrder": "v1"}}

here = os.path.dirname(__file__)
results = []
for st in STAGES:
    wf = build(st)
    fn = os.path.join(here, "WFP%d_%s.json" % (st["n"], st["slug"]))
    open(fn, "w").write(json.dumps(wf, indent=2))
    req = urllib.request.Request(N8N + "/api/v1/workflows", data=json.dumps(wf).encode(),
        headers={"X-N8N-API-KEY": PUB, "Content-Type": "application/json"}, method="POST")
    try:
        r = json.load(urllib.request.urlopen(req))
        results.append((wf["name"], r.get("id"), r.get("active")))
    except urllib.error.HTTPError as e:
        results.append((wf["name"], "ERROR %d" % e.code, e.read().decode()[:300]))
for name, wid, act in results:
    print("%-52s -> %s (active=%s)" % (name, wid, act))
