#!/usr/bin/env python3
"""Enrich WFP2/3/4/6/7 stage prompts with the REAL source-of-truth facts + content
rules + a smarter fact policy, so the pipeline produces grounded, cited content
instead of [VERIFY] shells. Reads the actual repo fact/rule files (single source of
truth), rebuilds the 'Run Stage Agent' prompt, PUTs to the existing workflow, and
rewrites the repo JSON. Re-run any time the fact/rule files change.
"""
import json, urllib.request, os
N8N = "https://voyagerscontent.app.n8n.cloud"
PUB = os.environ["N8N_PUB"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def readf(rel):
    t = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    return t.replace("{{DOMAIN}}", "galapagosislands.travel").replace("{{BRAND}}", "Galapagos Islands.Travel").replace("{{BRAND_ALT}}", "Galapagos Islands.Travel")

FACTS = ("=== MASTER FACTS (pre-verified — state confidently, cite the source) ===\n"
         + readf("context-pack/MASTER_FACTS_FILE.md") + "\n\n"
         + readf("context-pack/what-to-write-about/source-of-truth/GALAPAGOS_FACTS_ADDENDUM.md"))
RULES = ("=== CONTENT RULES / PAGE TEMPLATE (obey structure, schema, AIO, UX) ===\n"
         + readf("context-pack/what-to-write-about/page-templates/GUIDE_PAGE_SPEC.md"))

LAW = (
"BRAND: Galapagos Islands.Travel (galapagosislands.travel), an INDEPENDENT editorial guide. "
"Never 'Galapagos Travel Center'; never galapagosislands.com. Author: Juan Magallanes; contributors only "
"from the approved pool (Andre Robles/Voyagers Travel Company, Luisa Cordova/Golden Galapagos). "
"VOICE: honest, plain-spoken, answer-first, one idea per sentence, no padding. BANNED: #1, best, world-class, "
"paradise, hidden gem, luxury-as-filler, unforgettable, must-see, dream vacation. One CTA: 'Talk to a Galapagos "
"Specialist' (a lead, never 'Book Now'). No operator favoritism. Accent 'Galápagos' in body copy.\n")

POLICY = (
"=== FACT POLICY (READ CAREFULLY — this is why past drafts failed) ===\n"
"1. The FACTS block above is pre-verified source-of-truth. State anything in it CONFIDENTLY and cite its tag "
"([CDF]=Darwin Foundation, [GC]=Galápagos Conservancy, [GCT]=Conservation Trust, DPNG=National Park).\n"
"2. For well-established facts NOT in the block but widely documented by an authoritative body "
"(Darwin Foundation, IUCN Red List, Galápagos Conservancy, Galápagos National Park), STATE THEM PLAINLY and "
"attribute to that body. Do NOT mark these [VERIFY].\n"
"3. Use [VERIFY] ONLY for a specific number you genuinely cannot ground — and prefer a sourced range over [VERIFY].\n"
"4. NEVER invent a precise statistic. But a page that is mostly [VERIFY] is a FAILURE — it must be full of real, "
"grounded, cited facts with only a rare [VERIFY]. Honour the HARD TRUTHS (HT-1 timing, HT-2 islands/luxury) always.\n"
"5. If the title promises 'N facts', deliver N substantive, distinct facts — not N placeholders.\n")

def head(*blocks):  # assemble the shared context prefix
    return "=" + LAW + "\n" + FACTS + "\n\n" + RULES + "\n\n" + POLICY + "\n"

REC = "RECORD: {{ $json['Meta Title'] }} | brief: {{ $json['Topic / Brief'] }} | pillar: {{ $json['Pillar'] }} | page type: {{ $json['Page Type'] }}"

STAGES = {
 "WFP2_brief.json": ("cFY7Tz5q2ih2UCvt",
   "TASK — Produce the content brief. Include: exact target query; persona + funnel stage; full section outline "
   "(one H1, H2/H3 tree) per the CONTENT RULES; the 40-60 word answer-box target; 6-10 real FAQ (PAA) questions; "
   "required schema (Article+FAQPage+BreadcrumbList); and a bullet list of the SPECIFIC grounded facts (from the "
   "FACTS block, with tags) this page will use. Return STRICT JSON {\"brief_markdown\":\"...\"}.", ""),
 "WFP3_draft.json": ("eExgOTVFIoCuJb0D",
   "TASK — Write the FULL page draft from the brief, using the FACTS block as the factual backbone. Deliver real, "
   "substantive, cited content — NOT placeholders. Include: meta title (50-60 chars), meta description (140-160), "
   "one H1, clean H2/H3, a 40-60 word answer box, at least one data table, the full body per the CONTENT RULES, and "
   "a 6-10 question FAQ with 40-60 word answers, plus one CTA and internal links. Apply the FACT POLICY strictly "
   "(grounded+cited, minimal [VERIFY]). Return STRICT JSON {\"draft_markdown\":\"...\"}.",
   "BRIEF: {{ $json['Brief Content'] }}"),
 "WFP4_truthcheck.json": ("ZsrCHmeSCy8P4Wb2",
   "TASK — Truth-check the draft AGAINST the FACTS block and the FACT POLICY. Confirm: grounded facts are cited; any "
   "claim absent from FACTS is either attributed to an authoritative body or marked [VERIFY]; no invented numbers; "
   "HARD TRUTHS honoured; entity/brand rules met. FAIL if the page is mostly [VERIFY] shells or contradicts the FACTS. "
   "Return STRICT JSON {\"pass\":true|false,\"notes\":\"per-claim findings\"}.",
   "DRAFT: {{ $json['Draft Content'] }}"),
 "WFP6_polish.json": ("U0MrpTN3hv4RfNMI",
   "TASK — Final polish + assemble the production HTML per the CONTENT RULES: meta title/description, semantic "
   "H1/H2/H3, answer box, data table(s), FAQ accordion, related internal links, one CTA, and JSON-LD "
   "(Article with Person author 'Juan Magallanes' + BreadcrumbList + FAQPage; FAQ schema must byte-match the visible "
   "FAQ). Keep every grounded fact and citation intact. Return STRICT JSON {\"polished_html\":\"...\"}.",
   "HUMANIZED: {{ $json['Humanized Content'] }}"),
 "WFP7_auditor.json": ("na9GWyR851UHSlbP",
   "TASK — Auditor checklist: A Truth (facts grounded+cited per FACT POLICY; FAIL if mostly [VERIFY]); B Entity rules; "
   "C Voice (no banned words); D Audience+one CTA; E Structure+schema present and mirroring visible content per the "
   "CONTENT RULES; F Fidelity (no padding, answer-first); G Conversion safety. "
   "Return STRICT JSON {\"pass\":true|false,\"notes\":\"per-part PASS/FAIL\"}.",
   "PAGE: {{ $json['Polished Content'] }}"),
}

def put(wid, wf):
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": wf.get("settings", {"executionOrder":"v1"})}
    r = urllib.request.Request(N8N+"/api/v1/workflows/"+wid, data=json.dumps(body).encode(),
        headers={"X-N8N-API-KEY": PUB, "Content-Type":"application/json"}, method="PUT")
    try: return "ok" if json.load(urllib.request.urlopen(r)).get("id") else "??"
    except urllib.error.HTTPError as e: return "ERR %d %s"%(e.code, e.read().decode()[:160])

for fn,(wid, task, bodyref) in STAGES.items():
    p = os.path.join(os.path.dirname(__file__), fn); wf = json.load(open(p))
    prompt = head() + "\n" + task + "\n\n" + REC + ("\n\n"+bodyref if bodyref else "")
    for n in wf["nodes"]:
        if n["type"].endswith("langchain.anthropic"):
            n["parameters"]["messages"]["values"][0]["content"] = prompt
            n["parameters"].setdefault("options", {})["maxTokens"] = 20000
    open(p,"w").write(json.dumps(wf, indent=2))
    print("%-22s prompt=%d chars -> %s" % (fn, len(prompt), put(wid, wf)))
