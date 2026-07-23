#!/usr/bin/env python3
"""Post-humanizer chain for WFP5 (updated): normalize -> pattern-break -> dictionary.

Order (per the user):
  Finalize (code)
    -> Normalize (text-normalizer, no LLM)        strip invisible/junk chars; keep accents
    -> Pattern-Breaker (call)                      HTTP -> the standalone Pattern Breaker
                                                   workflow (Phase 1 deterministic detect;
                                                   Phase 2 = leashed, fact-guarded Sonnet on
                                                   flagged spans only). NOT LLM-free.
    -> PB Merge (code)                             take output_text, strip [[PB-REVIEW]] wrappers
                                                   (keep the original inner text), fall back to
                                                   the normalized artifact if PB failed
    -> De-AI Dictionary (human-dictionary, no LLM) ~1,170+ regex swaps for surviving AI terms;
                                                   MARKS every change into the "De-AI Log" field
    -> Output OK? -> Export to Drive -> Advance to Polishing | Needs Attention

text-normalizer and human-dictionary-travel are pure code. Pattern-Breaker is a
separate n8n workflow (vendored native build) called over HTTP so it owns its own
LLM node + credential and updates independently. All three are vendored under
engine/vendor/ via git subtree. Re-run this after a subtree pull.
"""
import json, os, urllib.request, urllib.error

# ── Pattern-Breaker toggle ────────────────────────────────────────────────
# SUSPENDED 2026-07-23 pending fine-tuning (it over-fired: ~183 spans / ~183
# Sonnet calls on a 1.6k-word page because it treats markdown table/list rows as
# mechanical spans). While False, WFP5 runs Normalize -> De-AI Dictionary and
# never calls the pattern-breaker workflow. Flip to True and re-run this applier
# to bring it back once thresholds are tuned. The standalone workflow itself is
# deactivated in n8n (not deleted), so it can also just be re-activated.
PB_ENABLED = False

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP5_humanize.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "yh9kMFkbPY34vmVJ"
PB_WID = "2ToiqCivCTCj74oK"          # standalone Pattern Breaker workflow
PB_WEBHOOK = N8N + "/webhook/pattern-breaker"

VENDOR = os.path.join(HERE, "..", "vendor")
NORM_NODE = os.path.join(VENDOR, "text-normalizer",
                         ".claude", "skills", "text-normalizer", "automation", "n8n_normalize_node.json")
DICT_WF = os.path.join(VENDOR, "human-dictionary-travel", "n8n", "n8n_workflow_code_node.json")

POST_NODES = ("Normalize (no-LLM)", "Pattern-Breaker (call)", "PB Merge (code)", "De-AI Dictionary (no-LLM)")


def normalize_js():
    d = json.load(open(NORM_NODE, encoding="utf-8"))
    node = d["nodes"][0] if isinstance(d, dict) and "nodes" in d else d
    js = node["parameters"]["jsCode"]
    js = js.replace("const INPUT_FIELD  = 'text';", "const INPUT_FIELD  = 'artifact';")
    js = js.replace("const OUTPUT_FIELD = 'text';", "const OUTPUT_FIELD = 'artifact';")
    return "const items = $input.all();\n" + js


def dictionary_js():
    wf = json.load(open(DICT_WF, encoding="utf-8"))
    js = [n for n in wf["nodes"] if n["type"].endswith("code")][0]["parameters"]["jsCode"]
    # split before the vendored n8n entry loop (kept forward-compatible: try both markers)
    for marker in ("const results = [];", "// n8n Code node"):
        if marker in js:
            engine = js[:js.index(marker)]
            break
    else:
        raise SystemExit("dictionary entry marker not found — vendored node changed shape")
    engine = engine.replace("const MAX_WORDS = 3000;", "const MAX_WORDS = 100000;")
    # legacy robustness patch (no-op on newer builds that already fixed the callback)
    engine = engine.replace(
        "out = out.replace(c.re, (match, _p1, offset, whole) => {",
        "out = out.replace(c.re, function (match) { var _a = arguments; "
        "var whole = _a[_a.length - 1]; var offset = _a[_a.length - 2];")
    wrapper = r"""
// --- WFP5 post-humanizer wrapper: swap surviving AI terms + MARK (with PB note) ---
const it = $input.first().json;
const art = String(it.artifact || '');
const r = humanize(art, '');
const detected = r.replacement_count > 0;
const sample = r.replacements.slice(0, 50).map(function (x) { return x.from + '→' + x.to; }).join('; ');
const dictNote = detected
  ? ('dictionary (no LLM): ' + r.replacement_count + ' swap(s) — ' + sample)
  : 'dictionary: no residual AI terms';
const deaiLog = (it.pbNote ? (it.pbNote + '\n') : '') + dictNote
  + (r.flag_count ? ('\ncontext-triggers flagged: ' + r.flag_count) : '');
return [{ json: {
  recordId: it.recordId || '', baseId: it.baseId || '', tableId: it.tableId || '',
  ok: it.ok === true, error: it.error || '', artifact: r.text,
  signals: it.signals || '', factGuard: it.factGuard || '',
  aiDetected: detected || !!it.pbNote, deaiLog: deaiLog
} }];
"""
    return engine + wrapper


PB_MERGE = r"""
// Merge Pattern-Breaker output back onto the item; strip review wrappers; fall back safely.
const norm = $('Normalize (no-LLM)').item.json;
const pb = $json || {};
let art = (pb && typeof pb.output_text === 'string' && pb.output_text.length > 40) ? pb.output_text : norm.artifact;
// [[PB-REVIEW]]…[[/PB-REVIEW]] wraps spans the fact-guard kept as ORIGINAL — keep inner text, drop markers
art = art.replace(/\[\[PB-REVIEW\]\]([\s\S]*?)\[\[\/PB-REVIEW\]\]/g, '$1').replace(/\[\[\/?PB-REVIEW\]\]/g, '');
const s = (pb && pb.summary) ? pb.summary : { spans_accepted: 0, spans_flagged_for_review: 0 };
const usedPB = typeof pb.output_text === 'string' && pb.output_text.length > 40;
const pbNote = usedPB
  ? ('pattern-breaker: ' + (s.spans_accepted || 0) + ' span(s) restructured, ' + (s.spans_flagged_for_review || 0) + ' flagged for review')
  : 'pattern-breaker: skipped (no output / call failed) — used normalized text';
return [{ json: {
  recordId: norm.recordId || '', baseId: norm.baseId || '', tableId: norm.tableId || '',
  ok: norm.ok === true, error: norm.error || '', artifact: art,
  signals: norm.signals || '', factGuard: norm.factGuard || '', pbNote: pbNote
} }];
"""


def code_node(name, js, pos, nid):
    return {"parameters": {"jsCode": js}, "id": nid, "name": name,
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}


def http_node(name, pos, nid):
    return {"parameters": {
        "method": "POST", "url": PB_WEBHOOK,
        "sendBody": True, "specifyBody": "keypair",
        "bodyParameters": {"parameters": [{"name": "text", "value": "={{ $json.artifact }}"}]},
        "options": {"timeout": 300000}},
        "id": nid, "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": pos, "onError": "continueRegularOutput"}


def main():
    wf = json.load(open(WF, encoding="utf-8"))
    # idempotent: drop any prior post-humanizer nodes + their connections
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in POST_NODES]
    for nm in POST_NODES:
        wf["connections"].pop(nm, None)
    nodes = {n["name"]: n for n in wf["nodes"]}

    norm = code_node("Normalize (no-LLM)", normalize_js(), [2000, 300], "post-normalize")
    dic = code_node("De-AI Dictionary (no-LLM)", dictionary_js(), [2540, 300], "post-dictionary")
    new_nodes = [norm, dic]

    for nm in ("Output OK?", "Export to Drive", "Advance to Polishing", "Route to Needs Attention"):
        if nm in nodes:
            nodes[nm]["position"] = [max(nodes[nm]["position"][0], 2720), nodes[nm]["position"][1]]

    c = wf["connections"]
    c["Finalize (code)"] = {"main": [[{"node": "Normalize (no-LLM)", "type": "main", "index": 0}]]}
    if PB_ENABLED:
        pbcall = http_node("Pattern-Breaker (call)", [2180, 300], "post-pattern-breaker")
        pbmerge = code_node("PB Merge (code)", PB_MERGE, [2360, 300], "post-pb-merge")
        new_nodes = [norm, pbcall, pbmerge, dic]
        c["Normalize (no-LLM)"] = {"main": [[{"node": "Pattern-Breaker (call)", "type": "main", "index": 0}]]}
        c["Pattern-Breaker (call)"] = {"main": [[{"node": "PB Merge (code)", "type": "main", "index": 0}]]}
        c["PB Merge (code)"] = {"main": [[{"node": "De-AI Dictionary (no-LLM)", "type": "main", "index": 0}]]}
    else:
        # SUSPENDED: skip pattern-breaker entirely — Normalize feeds Dictionary.
        c["Normalize (no-LLM)"] = {"main": [[{"node": "De-AI Dictionary (no-LLM)", "type": "main", "index": 0}]]}
    c["De-AI Dictionary (no-LLM)"] = {"main": [[{"node": "Output OK?", "type": "main", "index": 0}]]}

    wf["nodes"].extend(new_nodes)

    for nm in ("Export to Drive", "Advance to Polishing"):
        s = json.dumps(nodes[nm]["parameters"])
        s = s.replace("$('Finalize (code)')", "$('De-AI Dictionary (no-LLM)')")
        nodes[nm]["parameters"] = json.loads(s)
    nodes["Advance to Polishing"]["parameters"]["columns"]["value"]["De-AI Log"] = \
        "={{ $('De-AI Dictionary (no-LLM)').item.json.deaiLog }}"

    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    chain = ("Normalize -> Pattern-Breaker -> PB Merge -> Dictionary" if PB_ENABLED
             else "Normalize -> Dictionary  (Pattern-Breaker SUSPENDED)")
    print(f"WFP5 post-humanizer = {chain}. ({os.path.getsize(WF)//1024} KB)")

    pub = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not pub:
        print("no N8N key — wrote local JSON only."); return
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})}
    req = urllib.request.Request(N8N + "/api/v1/workflows/" + WID, data=json.dumps(body).encode(),
                                 headers={"X-N8N-API-KEY": pub, "Content-Type": "application/json"}, method="PUT")
    try:
        d = json.load(urllib.request.urlopen(req))
        print("pushed to n8n:", "ok" if d.get("id") else "??", "| active:", d.get("active"))
    except urllib.error.HTTPError as e:
        print("push ERR %d %s" % (e.code, e.read().decode()[:300]))


if __name__ == "__main__":
    main()
