#!/usr/bin/env python3
"""Build each stage's prompt from the REAL context-pack files and PUT it to n8n.

Routing follows AGENT_MANDATORY_BRIEFING's sub-step table (A-F) — that table is the
spec, not this script. Two principles, both learned the hard way:

1. GUARDRAILS AND INFO MUST RELATE TO CONTEXT. Never bulk-concatenate the pack into
   every stage (~3,500 lines / 150k+ chars). Each stage gets the shared LAW plus only
   the assets its sub-step needs; page-type assets resolve from the record's Page Type.
   Irrelevant rules produce padding and shoehorned paragraphs.

2. EVERY STAGE STATES ITS POSITION IN THE CHAIN. The stages share one head, so a stage
   that doesn't know where it sits judges artifacts by the wrong standard. WFP4 once
   failed a draft for carrying the very markers a draft is required to carry.

There is NO hand-written summary of the pack in this file. Earlier versions carried a
6-line 'LAW' paraphrase that silently replaced BRAND_STYLE_GUIDE, ENTITY_RULES, the
persona pack and the whole CTA system — the pipeline ran on the paraphrase and produced
generic CTAs and no UX. If a rule matters, it lives in a context-pack file and is loaded.

Re-run any time a context-pack file changes.
"""
import json, urllib.request, urllib.error, os, sys, time

N8N = "https://voyagerscontent.app.n8n.cloud"
PUB = os.environ["N8N_PUB"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CP = "context-pack/"


def readf(rel):
    t = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    return (t.replace("{{DOMAIN}}", "galapagosislands.travel")
             .replace("{{BRAND_ALT}}", "galapagosislands.travel")
             .replace("{{BRAND}}", "Galapagos Islands.Travel")
             .replace("{{PRIMARY_CTA}}", "the subtle dual footer close — travelers to Voyagers Travel Company, trade to Latin Trails (see CTA_BLOCK)")
             .replace("{{CTA_TRAVELER_URL}}", "https://www.voyagers.travel/galapagos")
             .replace("{{CTA_TRADE_URL}}", "https://www.latintrails.com")
             .replace("{{CONTRIBUTORS}}",
                      "Juan Magallanes (Galápagos Travel Advisor), Andre Robles (Voyagers Travel Company), "
                      "Luisa Cordova (Golden Galapagos)"))


def block(title, *rels):
    return "=== %s ===\n" % title + "\n\n".join(readf(r) for r in rels)


# ── shared head: the law every stage obeys (~250 lines) ───────────────────────
LAW = block("MANDATORY BRIEFING — read first, every run", CP + "AGENT_MANDATORY_BRIEFING.md")
ENTITY = block("ENTITY RULES", CP + "guardrails/ENTITY_RULES.md")
VOICE = block("BRAND VOICE — no deviation", CP + "brand-voice/BRAND_STYLE_GUIDE.galapagosislands-travel.yaml")
# The AUTHOR voice governs how bylined content is actually written and takes precedence over the
# style guide's generic 'we_sound_like'. Hardcoded into every prose stage per the user: content
# must sound like Juan Magallanes (distilled from 1,422 of his real advisory replies).
AUTHVOICE = block("AUTHOR VOICE — Juan Magallanes (governs the writing voice)",
                  CP + "brand-voice/AUTHOR_VOICE.juan-magallanes.md")
CTA_BLOCK = block("CTA — the subtle dual close (verbatim, every page)", CP + "guardrails/CTA_BLOCK.md")
FIDELITY = block("CONTENT FIDELITY", CP + "guardrails/CONTENT_FIDELITY.md")
HYGIENE = block("OUTPUT HYGIENE — the rules are not the content", CP + "guardrails/OUTPUT_HYGIENE.md")
HARD = block("HARD TRUTHS (constraints on every claim)", CP + "guardrails/GUARDIAN_OF_TRUTH.md")

HEAD = "\n\n".join([LAW, ENTITY, VOICE, AUTHVOICE, FIDELITY, HYGIENE, HARD]) + "\n"

# ── per-sub-step assets (loaded only where the briefing says they belong) ─────
# The DPNG site list must travel WITH the facts. MASTER_FACTS names galapagos_master.xlsx as a
# source and tells the writer to cite its sheets — but a workbook cannot enter a prompt, so the
# model was being told to cite data it could not see. It filled the gap from training and invented
# a [source:] tag for 'Cerro Dragon' (a real DPNG site, in that very sheet), and Truth Check
# rightly failed the page. Facts the model cannot read are not facts it can ground.
FACTS = block("FACTS — pre-verified source of truth (sub-step C)",
              CP + "MASTER_FACTS_FILE.md",
              CP + "what-to-write-about/source-of-truth/GALAPAGOS_FACTS_ADDENDUM.md",
              CP + "what-to-write-about/source-of-truth/DPNG_VISITOR_SITES.md")
AUDIENCE = block("AUDIENCE & CONVERSION (sub-step A)",
                 CP + "who-to-write-for/PERSONA_PACK.galapagosislands-travel.yaml")
PROCEDURE = block("GENERATION PROCEDURE — run in order, do not skip",
                  CP + "CONTENT_GENERATION_PROMPT.md")
REGISTRY = block("PAGE-TYPE REGISTRY", CP + "what-to-write-about/page-templates/PAGE_TYPES.md")
MMPROC = block("MARKETMUSE GATE (hub/pillar only)", CP + "what-to-write-about/MARKETMUSE_PROCESS.md")
AUDITOR = block("AUDITOR CHECKLIST — your checklist, run every part",
                CP + "guardrails/AUDITOR_PROMPT.md")
CONVERSION = block("CONVERSION EXPERT", CP + "guardrails/CONVERSION_EXPERT.md")

# page-type blueprint (sub-step B) — resolved per record at runtime, see PAGETYPE_SWITCH
SPEC_GUIDE = block("PAGE-TYPE BLUEPRINT — guide",
                   CP + "what-to-write-about/page-templates/GUIDE_PAGE_SPEC.md")
SPEC_HUB = block("PAGE-TYPE BLUEPRINT — hub",
                 CP + "what-to-write-about/page-templates/TEMPLATE-SPEC.md")
ITIN_RULE = block("ITINERARY RATING RULE (context-scoped)",
                  CP + "guardrails/ITINERARY_RATING_RULE.md")

# Guide pages carry NO Review/AggregateRating (PAGE_TYPES registry); hub/vessel/hotel may,
# but only with genuine verifiable reviews. Stated here so the writing stages can't drift.
PAGETYPE_NOTE = (
    "=== PAGE-TYPE SELECTION ===\n"
    "This record's Page Type is given in RECORD below. Build to THAT type's blueprint.\n"
    "- Guide / FAQ / wildlife / island → the 'guide' blueprint. Schema: Article + FAQPage +\n"
    "  BreadcrumbList + speakable. NO Review/AggregateRating — this is editorial content with\n"
    "  no reviews to cite, and fabricated rating schema risks a Google manual action.\n"
    "- Hub / Pillar → the 'hub' blueprint. Review/AggregateRating allowed ONLY with genuine,\n"
    "  verifiable reviews.\n"
    "If both blueprints are loaded, use the one matching Page Type and ignore the other.\n")

REC = ("RECORD: {{ $json['Meta Title'] }} | brief: {{ $json['Topic / Brief'] }} | "
       "pillar: {{ $json['Pillar'] }} | PAGE TYPE: {{ $json['Page Type'] }} | "
       "primary keyword: {{ $json['Primary Keyword'] }}")

HUMAN = ("HUMAN ENRICHMENT (verbatim, never paraphrase — sub-step D2; empty = skip):\n"
         "Contributor: {{ $json['Contributor'] }}\n"
         "Human Paragraphs: {{ $json['Human Paragraphs'] }}\n"
         "Human Quotes: {{ $json['Human Quotes'] }}\n"
         "Anecdotes: {{ $json['Anecdotes'] }}")

# Hub/Pillar pages stop at a human MarketMuse gate after the brief; the terms come back on the
# record. Empty for every other page type — those never stop. See MARKETMUSE_PROCESS.md.
MM = ("MARKETMUSE TARGET TERMS (hub/pillar only; empty = none, ignore this block):\n"
      "Score: {{ $json['MarketMuse Score'] }}\n"
      "Terms: {{ $json['Target Keywords (NW/MM)'] }}\n"
      "These are a COVERAGE CHECKLIST, not a quota. Work them in only where they genuinely fit the "
      "brief's outline and read naturally. Never stuff a term, never bend a sentence around one, "
      "and never let a term override the FACTS, the HARD TRUTHS or the brand voice — a term with no "
      "honest place on the page is left out. The Score is a gate and a record: never publish it, "
      "never mention it in copy.")

# Written before Scoring by WFPT (trend) and WFPE (E-E-A-T). Every Proprietary Stats line already
# carries its own [source: …] tag; the placeholders are CONTENT (yellow blocks a human fills at
# Editor Review), not markers — Polishing keeps them, the Auditor must not flag them.
EVIDENCE = ("EVIDENCE PACK (gathered before Scoring — verbatim, never paraphrase; empty = skip):\n"
            "Information Gain Angle: {{ $json['Information Gain Angle'] }}\n"
            "Proprietary Stats (each line already carries its [source: …] tag — reproduce the tag "
            "exactly): {{ $json['Proprietary Stats'] }}\n"
            "Real PAA Questions (pulled from the live SERP — use these, do not invent your own): "
            "{{ $json['PAA Questions'] }}\n"
            "Seasonality: {{ $json['Seasonality Window'] }}\n"
            "Evidence Placeholders (yellow HTML blocks marking gaps a human fills at Editor Review "
            "— place them VERBATIM under the heading they belong to; never delete one, never rewrite "
            "one, and never write copy that pretends the gap is already filled): "
            "{{ $json['Evidence Placeholders'] }}")

# ── stage table: (workflow id, head-extras, stage framing + task, body refs) ──
STAGES = {
 "WFP2_brief.json": ("cFY7Tz5q2ih2UCvt", [REGISTRY, PAGETYPE_NOTE, SPEC_GUIDE, SPEC_HUB, AUDIENCE, FACTS, ITIN_RULE, MMPROC],
   "STAGE — Brief Ready. You run sub-steps A (audience & conversion mapping), B (page-type "
   "blueprint) and C (facts grounding) per the MANDATORY BRIEFING.\n"
   "If this record's Page Type is Hub Page or Pillar Page, the pipeline STOPS after you and waits "
   "for a human MarketMuse pass. Your brief is what that person reads. End it with a short "
   "'MarketMuse pass' section naming the exact topic/query to run and what you most want term "
   "coverage on, so they can act without reverse-engineering the brief. For any other Page Type "
   "there is no gate — say nothing about MarketMuse.\n"
   "TASK — Produce the content brief. Lock and state: primary/secondary persona; funnel stage; "
   "primary CTA verbatim from the persona pack's cta_system; objections_to_preempt (ids from the "
   "objection library). Then the section outline (one H1, H2/H3 tree) in the blueprint's canonical "
   "section order for THIS Page Type; the 40-60 word answer-box target; the Real PAA Questions from the evidence pack used VERBATIM (do not invent PAA questions — if the pack supplies none, write 6-10 and mark them unverified); "
   "the required schema profile for this page type; and a bullet list of the SPECIFIC grounded "
   "facts (with their [source: …]) the page will use.\nThen an EVIDENCE & INFORMATION GAIN section: for EACH Proprietary Stats line, name the exact H2/H3 in your outline where it lands; state the Information Gain Angle as the one thing this page says that no ranking page does; and name the heading each Evidence Placeholder block sits under. Never invent an evidence asset — if the pack is empty, say so and omit the section. Tying each asset to a named heading is what makes the draft place it instead of ignoring it. Return STRICT JSON {\"brief_markdown\":\"...\"}.",
   EVIDENCE),

 "WFP3_draft.json": ("eExgOTVFIoCuJb0D", [REGISTRY, PAGETYPE_NOTE, SPEC_GUIDE, SPEC_HUB, AUDIENCE, FACTS, PROCEDURE, ITIN_RULE],
   "STAGE — Drafting. You run sub-steps C, D (brand-voice drafting) and D2 (human enrichment). "
   "This draft is INTERNAL — no reader sees it. Tag grounded claims inline [source: <file/sheet>] "
   "per GUARDIAN_OF_TRUTH rule 1 so Truth Check can verify them; Polishing strips them later.\n"
   "TASK — Write the FULL page draft from the brief, following the GENERATION PROCEDURE in order "
   "and the blueprint for this Page Type. Real substantive grounded content, not placeholders. "
   "Include: meta title (50-60 chars — COUNT THEM, hard gate), meta description (140-160), one H1, "
   "clean H2/H3, a 40-60 word answer box, at least one data table, the full body, a 6-10 question "
   "FAQ with 40-60 word answers, one primary CTA and internal links. Place every Proprietary Stats line where the brief assigns it, reproducing its [source: …] tag exactly. Lead with the Information Gain Angle. Place each Evidence Placeholder block VERBATIM under the heading the brief names — they are content, not markers: never delete, never rewrite, never paper over the gap. Place any HUMAN ENRICHMENT "
   "verbatim and attribute it. Obey OUTPUT HYGIENE — never recite a rule as a sentence. "
   "Return STRICT JSON {\"draft_markdown\":\"...\"}.",
   "BRIEF: {{ $json['Brief Content'] }}\n\n" + MM + "\n\n" + HUMAN + "\n\n" + EVIDENCE),

 "WFP4_truthcheck.json": ("ZsrCHmeSCy8P4Wb2", [FACTS],
   "STAGE — Truth Check. You are checking an INTERNAL DRAFT, three stages before publication. "
   "[source: …] / [VERIFY] / [human: …] markers SHOULD be present — that is the draft doing its "
   "job. Stripping them is Polishing's task, not yours. NEVER fail a draft for carrying markers "
   "and never remark that polish 'was not run' — it runs after you. Judge FACTS ONLY.\n"
   "TASK — Run the GUARDIAN_OF_TRUTH Truth Check procedure against the FACTS. For each factual "
   "sentence confirm a [source: …] tag traceable to the facts; verify entity rules; confirm HARD "
   "TRUTHS honoured as constraints. Human-tagged [human: …] text is exempt from the source rule "
   "but must not contradict the facts — flag [VERIFY], never alter or drop it. FAIL ONLY for: an "
   "untagged factual claim, a claim contradicting the FACTS, an invented statistic, a HARD TRUTH "
   "violation, or a page that is mostly [VERIFY]. A derived estimate framed as one ('roughly', "
   "'~') and consistent with the facts is acceptable — note it, don't fail it. "
   "Return STRICT JSON {\"pass\":true|false,\"notes\":\"per-claim findings\"}.",
   "DRAFT: {{ $json['Draft Content'] }}"),

 "WFP5_humanize.json": ("yh9kMFkbPY34vmVJ", [],
   "STAGE — Humanizing. Between Truth Check and Polishing, still an INTERNAL artifact. Markers "
   "belong here: KEEP every [source: …] / [VERIFY] / [human: …] for Polishing to resolve. Do not "
   "strip or flag them.\n"
   "TASK — Rewrite for natural human cadence WITHOUT changing facts, numbers, sources, markers or "
   "structure. Human-authored [human: …] text stays VERBATIM — never smooth it. If the draft "
   "recites a rule as a sentence (OUTPUT HYGIENE §1), CUT it rather than improve its prose.\n"
   "DE-AI RULES (a deterministic detector checks these AFTER you — anything that survives is sent "
   "back for reconstruction, so do it now):\n"
   "1. NO EM-DASHES (—). Juan never uses them. Use a comma, a period, a colon, or parentheses.\n"
   "2. BURSTINESS. Human writing mixes long, complex sentences with short, punchy ones and the odd "
   "fragment. Do NOT keep a uniform sentence length. Aim for a sentence-length coefficient of "
   "variation ≥ 0.5 — vary deliberately.\n"
   "3. BANNED AI VOCABULARY. Never use: delve, tapestry, cornerstone, pivotal, multifaceted, "
   "paradigm, robust, holistic, seamless, vibrant, bustling, myriad, plethora, underscore, "
   "showcase, foster, garner, leverage, elevate, unleash, moreover, furthermore, 'it is worth "
   "noting', 'plays a crucial role', 'a testament to', 'in conclusion', 'to summarize', and the "
   "like. Say the plain thing instead (the full list is enforced in code).\n"
   "4. No empty transitions, no both-sides hedging, no moralizing conclusion. Answer-first, "
   "specifics over adjectives, in Juan's voice.\n"
   "5. No invisible characters, no smart-quote clutter, no model artifacts.\n"
   "Return STRICT JSON {\"humanized_markdown\":\"...\"}.",
   "DRAFT: {{ $json['Draft Content'] }}"),

 "WFP6_polish.json": ("U0MrpTN3hv4RfNMI", [REGISTRY, PAGETYPE_NOTE, SPEC_GUIDE, SPEC_HUB, AUDIENCE, CONVERSION, CTA_BLOCK],
   "STAGE — Polishing. THE PUBLICATION BOUNDARY. Everything upstream was internal; everything you "
   "emit is reader-facing. Stripping the internal markers is YOUR job and no one else's.\n"
   "TASK — Two outputs.\n"
   "(1) polished_html — a COMPLETE, VALID HTML DOCUMENT the CMS can ingest. It MUST open with "
   "<!DOCTYPE html><html lang=\"en\"><head> and contain a real <title> element (50-60 chars — COUNT "
   "THEM), a real <meta name=\"description\"> (140-160), <link rel=\"canonical\">, then <body>. Do NOT "
   "put the meta title or description in an HTML comment — a comment is not a tag and the CMS "
   "cannot read it. Emit PURE HTML: no markdown syntax anywhere, ever. Never '**bold**' (use "
   "<strong>), never '~' for approx (write 'about' or '&approx;'), never markdown pipes for tables "
   "(use <table>). Markdown inside a table cell ships literal asterisks to the reader.\n"
   "Build per this Page Type's blueprint: semantic H1/H2/H3, answer box, data table(s), "
   "FAQ accordion, related links, and JSON-LD (Article with Person author 'Juan "
   "Magallanes' + BreadcrumbList + FAQPage; FAQ schema byte-matches the visible FAQ). "
   "END THE PAGE with the subtle dual close from the CTA BLOCK, VERBATIM: travelers → Voyagers "
   "Travel Company (full planning), trade → Latin Trails (Galápagos DMC). Both company names must "
   "appear exactly once, at the foot, quietly — no loud CTA band, no 'Talk to a Specialist', no "
   "'Book Now'. Link them to CTA_TRAVELER_URL and CTA_TRADE_URL. Keep every "
   "grounded FACT and all human-authored text intact, but make it reader-facing: STRIP every "
   "[source: …] / [VERIFY] / [human: …] marker from body, tables, FAQ and JSON-LD — zero may "
   "survive. Replace with prose attribution only where a fact is notable, surprising or contested, "
   "and close with a short 'Sources' line. Keep human text verbatim with its visible attribution. "
   "Delete any sentence that recites a rule (OUTPUT HYGIENE §1).\n"
   "(2) conversion_review — run the CONVERSION EXPERT and return its block. Instructions for the "
   "webmaster, never page copy. The funnel stays SUBTLE: this is an editorial guide and a visible "
   "funnel destroys the trust the funnel depends on.\n"
   "(3) section_guide — a JSON array, one entry per heading in the page, IN DOCUMENT ORDER: "
   "{\"level\":1|2|3, \"heading\":\"<exact heading text as it appears>\", \"purpose_es\":\"<one "
   "sentence IN SPANISH saying what this section is for and what the webmaster should watch when "
   "placing it>\"}. The heading text must match the page EXACTLY — it is used to anchor the "
   "webmaster's instructions. purpose_es is for the webmaster and is never published.\n"
   "Return STRICT JSON {\"polished_html\":\"...\",\"conversion_review\":\"...\",\"section_guide\":[...]}.",
   # On a retry the record carries the measured failure. Character counts are measured in code,
   # not by you — if it says 167, it is 167, however many you counted.
   "PREVIOUS ATTEMPT (empty on the first run — if present, FIX EXACTLY THIS and change nothing "
   "else): {{ $json['Last Error'] }}\n\n"
   "HUMANIZED: {{ $json['Humanized Content'] }}"),

 "WFP7_auditor.json": ("na9GWyR851UHSlbP", [REGISTRY, PAGETYPE_NOTE, SPEC_GUIDE, SPEC_HUB, AUDIENCE, FACTS, AUDITOR, CTA_BLOCK],
   "STAGE — Auditor Review. You see TWO artifacts. Judge each by its own standard:\n"
   "- DRAFT (internal, below): carries [source: …] markers. Use it for Part A grounding — every "
   "factual claim traceable. Its markers are CORRECT; never fail them.\n"
   "- PAGE (published build, below): must be clean. Use it for every other part.\n"
   "TASK — Run the AUDITOR CHECKLIST, every part, against the right artifact. Additionally:\n"
   "Part H LEAKAGE — HARD FAIL, check FIRST, character by character, on PAGE only: (h1) zero "
   "'[source:' '[VERIFY]' '[human:' '[HT-' '[GC]' '[GCT]' '[CDF]' '[DPNG]' '[MASTER FACTS]' "
   "anywhere, INCLUDING inside JSON-LD; (h2) no guardrail recited as copy and no stock HT-1/HT-2 "
   "paragraph on a page whose topic is neither timing nor luxury (OUTPUT HYGIENE §1-2).\n"
   "Part I META PRESENCE — check only that a real <title> ELEMENT and a real "
   "<meta name=\"description\"> EXIST ('<!-- META TITLE ... -->' is a comment, not a tag — that is "
   "a FAIL). **Do NOT count their characters and never fail on length.** Length is measured and "
   "enforced deterministically in code at Polishing, before you ever see the page. You cannot "
   "count reliably: you have reported a 163-char description as '158' and a 140-char one as '137', "
   "the second of which wrongly blocked a correct page. If it reached you, its lengths already "
   "passed. Report 'present' or 'missing', nothing more.\n"
   "Part J SCHEMA BY TYPE — a guide page carrying Review/AggregateRating is a FAIL.\n"
   "Part K VALID HTML — the page must be a complete HTML document (<!DOCTYPE html><html><head>...). "
   "FAIL on any markdown surviving in it: '**bold**', markdown pipe-tables, or a bare '~' meaning "
   "'approximately'. Those ship literal asterisks and tildes to the reader. Quote each instance.\n"
   "Part L CTA CLOSE — FAIL unless the page ends with the subtle dual close and BOTH 'Voyagers "
   "Travel Company' and 'Latin Trails' appear (travelers→Voyagers, trade→Latin Trails, per the CTA "
   "BLOCK). Also FAIL if the retired 'Talk to a Galápagos Specialist' CTA still appears, or if the "
   "close is a loud sales band rather than a subtle footer.\n"
   "Part C VOICE also covers AUTHOR VOICE: the prose must read like Juan Magallanes — answer-first, "
   "candid 'but'-caveats, specifics over adjectives — not generic marketing copy.\n"
   "Quote the offending text for every FAIL. Return STRICT JSON "
   "{\"pass\":true|false,\"notes\":\"per-part PASS/FAIL\"}.",
   "PAGE: {{ $json['Polished Content'] }}\n\nDRAFT (for Part A grounding only): {{ $json['Draft Content'] }}"),
}


def put(wid, wf):
    """Never raise, always return a printable status.

    This used to be a bare urlopen(). Each PUT is ~300 KB, and a single transient
    timeout / reset raised an exception that was NOT an HTTPError, so it escaped the
    handler and killed the whole loop — every stage after it was silently never
    pushed and the run looked like it had merely 'stopped early'.
    """
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})}
    payload = json.dumps(body).encode()
    r = urllib.request.Request(N8N + "/api/v1/workflows/" + wid, data=payload,
                               headers={"X-N8N-API-KEY": PUB, "Content-Type": "application/json"}, method="PUT")
    for attempt in (1, 2, 3):
        try:
            with urllib.request.urlopen(r, timeout=180) as resp:
                return "ok" if json.load(resp).get("id") else "?? unexpected response body"
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                detail = "(no body)"
            return "ERR %d %s" % (e.code, detail)          # a real rejection: do not retry
        except Exception as e:
            if attempt == 3:
                return "ERR %s: %s (payload %d bytes, 3 attempts)" % (
                    type(e).__name__, e, len(payload))
            time.sleep(3 * attempt)
    return "ERR unreachable"


failures = []
for fn, (wid, extras, task, bodyref) in STAGES.items():
    p = os.path.join(os.path.dirname(__file__), fn)
    try:
        with open(p, encoding="utf-8") as fh:
            wf = json.load(fh)
        prompt = HEAD + "\n" + "\n\n".join(extras) + "\n\n" + task + "\n\n" + REC + (("\n\n" + bodyref) if bodyref else "")
        # Only the primary stage agent — never secondary anthropic nodes like
        # WFP5's "Reconstruct (Andre-Juan)", which owns its own prompt.
        hits = [n for n in wf["nodes"]
                if n["type"].endswith("langchain.anthropic") and n["name"] == "Run Stage Agent"]
        if len(hits) != 1:
            raise RuntimeError("expected exactly 1 'Run Stage Agent' anthropic node, found %d" % len(hits))
        hits[0]["parameters"]["messages"]["values"][0]["content"] = prompt
        hits[0]["parameters"].setdefault("options", {})["maxTokens"] = 20000
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(wf, indent=2))
        status = put(wid, wf)
    except Exception as e:                                  # one bad stage must not hide the rest
        status = "ERR %s: %s" % (type(e).__name__, e)
        prompt = ""
    if not status.startswith("ok"):
        failures.append("%s: %s" % (fn, status))
    print("%-22s prompt=%6d chars -> %s" % (fn, len(prompt), status), flush=True)

if failures:
    # Printed only on failure. The CI step greps every line for '-> ok', so a summary
    # on the happy path would read as a failed stage.
    print("FAILED STAGES (%d):" % len(failures), flush=True)
    for f in failures:
        print("  " + f, flush=True)
    sys.exit(1)
