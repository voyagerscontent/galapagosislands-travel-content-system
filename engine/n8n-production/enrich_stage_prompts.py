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
"1. The FACTS block above is pre-verified source-of-truth. State anything in it CONFIDENTLY.\n"
"2. For well-established facts NOT in the block but widely documented by an authoritative body "
"(Darwin Foundation, IUCN Red List, Galápagos Conservancy, Galápagos National Park), STATE THEM PLAINLY and "
"attribute to that body. Do NOT mark these [VERIFY].\n"
"3. Use [VERIFY] ONLY for a specific number you genuinely cannot ground — and prefer a sourced range over [VERIFY].\n"
"4. NEVER invent a precise statistic. But a page that is mostly [VERIFY] is a FAILURE — it must be full of real, "
"grounded facts with only a rare [VERIFY]. Honour the HARD TRUTHS (HT-1 timing, HT-2 islands/luxury) always.\n"
"5. If the title promises 'N facts', deliver N substantive, distinct facts — not N placeholders.\n")

# The tags exist so the truth-checker can verify grounding. They are a DRAFT-STAGE
# artifact and must never reach a reader. Past pages shipped 100+ '[GCT][CDF]' in body
# copy and inside JSON-LD; this block is what stops that.
GROUNDING = (
"=== GROUNDING MARKERS (internal — never published) ===\n"
"[CDF]=Darwin Foundation, [GC]=Galápagos Conservancy, [GCT]=Conservation Trust, [DPNG]=National Park.\n"
"These are INTERNAL provenance markers for the truth-checker. They are NOT reader-facing citations and NOT a "
"house style. Those four are the ONLY valid markers — never invent others ([HT-2], [MASTER FACTS] etc. are labels "
"for YOUR reference, never text).\n"
"They are REQUIRED at draft stage and FORBIDDEN at publication. Which one applies depends on the stage you are "
"running — your TASK below states it. Never judge an artifact by the other stage's standard.\n"
"- DRAFT / TRUTH CHECK: markers SHOULD be present. The draft is an internal artifact — no reader sees it. Their "
"presence here is correct and is NOT a defect.\n"
"- POLISH onward: a reader-facing page containing a single marker is a defect.\n"
"- HUMANIZE / POLISH: STRIP every marker. Convert to reader-facing attribution: name the body in prose where the "
"fact is notable, surprising, or contested ('the Charles Darwin Foundation records about 350'), and close the page "
"with a short 'Sources' line naming the bodies used. Do NOT attribute every sentence — that reads like a footnoted "
"term paper, not a travel guide.\n"
"- [VERIFY] is likewise a working marker: resolve it or cut the claim before polish. It must never be published.\n")

# LAW / HARD TRUTHS are constraints on what may be claimed. Past pages recited them as
# body copy ('no operator favoritism', 'Luxury is the boat, not the map'), and shoehorned
# stock HT-1/HT-2 paragraphs into pages with no bearing on timing or luxury.
HYGIENE = (
"=== OUTPUT HYGIENE (the rules are not the content) ===\n"
"Everything above — the LAW, the HARD TRUTHS, the CONTENT RULES, this policy — tells you what you MAY and MAY NOT "
"write. None of it is material to write ABOUT. Obey it silently.\n"
"1. NEVER restate a rule as a sentence. Banned verbatim-style leakage: 'an honest trade-off, not a ranking', "
"'with no operator favoritism', 'an independent editorial guide', 'Luxury is the boat, not the map', 'we don't "
"play favorites'. If a sentence's real subject is your own editorial stance, cut it.\n"
"2. HT-1 (timing) and HT-2 (islands/luxury) are PROHIBITIONS, not paragraphs. You honour HT-1 by never calling a "
"month 'best' — not by announcing 'the Galápagos is a year-round destination'. You honour HT-2 by never implying "
"an island makes a boat luxurious — not by declaring 'no island is better than another'. Write about timing or "
"luxury ONLY when the page's topic is timing or luxury. A land-iguana facts page needs neither.\n"
"3. No meta-commentary about the page, the brand's independence, or your process. Readers came for the answer.\n"
"4. No internal markers in reader-facing output — see GROUNDING MARKERS above.\n")

def head(*blocks):  # assemble the shared context prefix
    return ("=" + LAW + "\n" + FACTS + "\n\n" + RULES + "\n\n" + POLICY + "\n"
            + GROUNDING + "\n" + HYGIENE + "\n")

REC = "RECORD: {{ $json['Meta Title'] }} | brief: {{ $json['Topic / Brief'] }} | pillar: {{ $json['Pillar'] }} | page type: {{ $json['Page Type'] }}"

STAGES = {
 "WFP2_brief.json": ("cFY7Tz5q2ih2UCvt",
   "TASK — Produce the content brief. Include: exact target query; persona + funnel stage; full section outline "
   "(one H1, H2/H3 tree) per the CONTENT RULES; the 40-60 word answer-box target; 6-10 real FAQ (PAA) questions; "
   "required schema (Article+FAQPage+BreadcrumbList); and a bullet list of the SPECIFIC grounded facts (from the "
   "FACTS block, with tags) this page will use. Return STRICT JSON {\"brief_markdown\":\"...\"}.", ""),
 "WFP3_draft.json": ("eExgOTVFIoCuJb0D",
   "TASK — Write the FULL page draft from the brief, using the FACTS block as the factual backbone. Deliver real, "
   "substantive, grounded content — NOT placeholders. Include: meta title (50-60 chars — count them, this is a hard "
   "gate), meta description (140-160), one H1, clean H2/H3, a 40-60 word answer box, at least one data table, the "
   "full body per the CONTENT RULES, and a 6-10 question FAQ with 40-60 word answers, plus one CTA and internal "
   "links. Apply the FACT POLICY strictly (grounded, minimal [VERIFY]). This draft is INTERNAL: tag grounded claims "
   "with [GC]/[GCT]/[CDF]/[DPNG] inline so the truth-checker can verify them — a later stage strips them. Obey "
   "OUTPUT HYGIENE: never recite a rule as a sentence. Return STRICT JSON {\"draft_markdown\":\"...\"}.",
   "BRIEF: {{ $json['Brief Content'] }}"),
 "WFP4_truthcheck.json": ("ZsrCHmeSCy8P4Wb2",
   "STAGE — You are checking an INTERNAL DRAFT, four stages before publication. Grounding markers "
   "([GC]/[GCT]/[CDF]/[DPNG]) SHOULD be present here: that is the draft doing its job, and stripping them is the "
   "POLISH stage's task, not yours. NEVER fail a draft for containing markers, and never remark that polish 'was not "
   "run' — it runs after you. Judge FACTS ONLY.\n"
   "TASK — Truth-check the draft AGAINST the FACTS block and the FACT POLICY. Confirm: grounded claims carry a "
   "marker; any claim absent from FACTS is either attributed to an authoritative body or marked [VERIFY]; no invented "
   "numbers; HARD TRUTHS honoured as constraints; entity/brand rules met. FAIL ONLY for: a claim that contradicts "
   "FACTS, an invented/ungrounded statistic, a HARD TRUTH violation, or a page that is mostly [VERIFY] shells. "
   "A derived estimate is acceptable if framed as one ('roughly', '~') and consistent with FACTS — note it, don't "
   "fail it. Return STRICT JSON {\"pass\":true|false,\"notes\":\"per-claim findings\"}.",
   "DRAFT: {{ $json['Draft Content'] }}"),
 "WFP6_polish.json": ("U0MrpTN3hv4RfNMI",
   "STAGE — You are the PUBLICATION BOUNDARY. Everything upstream was internal; everything you emit is reader-facing. "
   "Stripping the grounding markers is YOUR job and no one else's.\n"
   "TASK — Final polish + assemble the production HTML per the CONTENT RULES: meta title (50-60 chars — COUNT THEM, "
   "hard gate), meta description (140-160), semantic H1/H2/H3, answer box, data table(s), FAQ accordion, related "
   "internal links, one CTA, and JSON-LD (Article with Person author 'Juan Magallanes' + BreadcrumbList + FAQPage; "
   "FAQ schema must byte-match the visible FAQ).\n"
   "THIS IS THE PUBLICATION BOUNDARY. Keep every grounded FACT intact, but the page must now be reader-facing:\n"
   "- STRIP every [GC]/[GCT]/[CDF]/[DPNG]/[VERIFY] marker from body, tables, FAQ and JSON-LD. Zero may survive.\n"
   "- Replace them with prose attribution ONLY where the fact is notable, surprising or contested, and close with a "
   "short 'Sources' line naming the bodies. Most sentences need no attribution.\n"
   "- Delete any sentence that recites a rule rather than informing the reader (see OUTPUT HYGIENE).\n"
   "Return STRICT JSON {\"polished_html\":\"...\"}.",
   "HUMANIZED: {{ $json['Humanized Content'] }}"),
 "WFP5_humanize.json": ("yh9kMFkbPY34vmVJ",
   "STAGE — You are between TRUTH CHECK and POLISH, still working on an INTERNAL artifact. Grounding markers belong "
   "here: KEEP them for polish to resolve. Do not strip them and do not flag them.\n"
   "TASK — Humanize the draft: vary sentence rhythm, cut padding and AI tells, keep it plain-spoken and answer-first. "
   "Change HOW it reads, never WHAT it claims — every grounded fact, figure and [TAG] marker must survive this stage "
   "intact for the polish step to resolve. Obey OUTPUT HYGIENE: if the draft recites a rule as a sentence "
   "('no operator favoritism', a stock year-round/no-island-is-better paragraph on a page that isn't about timing or "
   "luxury), CUT it — do not smooth it into better prose. Return STRICT JSON {\"humanized_markdown\":\"...\"}.",
   "DRAFT: {{ $json['Draft Content'] }}"),
 "WFP7_auditor.json": ("na9GWyR851UHSlbP",
   "TASK — Auditor checklist: A Truth (facts grounded per FACT POLICY; FAIL if mostly [VERIFY]); B Entity rules; "
   "C Voice (no banned words); D Audience+one CTA; E Structure+schema present and mirroring visible content per the "
   "CONTENT RULES; F Fidelity (no padding, answer-first); G Conversion safety; "
   "H LEAKAGE — HARD FAIL, check this FIRST and character-by-character: (h1) the page contains ZERO internal markers "
   "'[GC]' '[GCT]' '[CDF]' '[DPNG]' '[VERIFY]' anywhere including inside JSON-LD; (h2) the page never recites its own "
   "guardrails as copy ('an honest trade-off, not a ranking', 'with no operator favoritism', 'an independent "
   "editorial guide', 'Luxury is the boat, not the map') and carries no stock HT-1/HT-2 paragraph on a page whose "
   "topic is neither timing nor luxury; "
   "I TITLE LENGTH — count the <title> characters and report the integer; FAIL if outside 50-60. "
   "Quote the offending text for every FAIL. Return STRICT JSON {\"pass\":true|false,\"notes\":\"per-part PASS/FAIL\"}.",
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
