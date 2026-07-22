#!/usr/bin/env python3
"""Add the deterministic, LLM-FREE post-humanizer step to WFP5.

After the LLM humanize + Andre<->Juan reconstruction (which handle prose), two
vendored skills run as pure code — no model, no network, byte-for-byte
reproducible:

  Finalize (code)
    -> Normalize (text-normalizer, no LLM)      strip invisible/junk chars, smart
                                                quotes/dashes; keeps accents (Galápagos)
    -> De-AI Dictionary (human-dictionary, no LLM)  ~1,170 regex rules swap any AI
                                                terms that survived for plain human/
                                                travel wording; MARKS what it changed
    -> Output OK? -> Export to Drive -> Advance to Polishing | Needs Attention

"Use the dictionary when AI is detected, and mark it": the dictionary only
matches AI vocabulary, so a non-zero replacement count IS the detection. The
list of swaps is written to the record's "De-AI Log" field, so every page
carries a visible mark of what deterministic de-AI touched it.

Both engines are vendored via git subtree under engine/vendor/ and will be
updated there (git subtree pull). This applier re-embeds their compiled JS into
the nodes; re-run it after pulling a vendor update.
"""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP5_humanize.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "yh9kMFkbPY34vmVJ"

VENDOR = os.path.join(HERE, "..", "vendor")
NORM_NODE = os.path.join(VENDOR, "text-normalizer",
                         ".claude", "skills", "text-normalizer", "automation", "n8n_normalize_node.json")
DICT_WF = os.path.join(VENDOR, "human-dictionary-travel", "n8n", "n8n_workflow_code_node.json")


def normalize_js():
    d = json.load(open(NORM_NODE, encoding="utf-8"))
    node = d["nodes"][0] if isinstance(d, dict) and "nodes" in d else d
    js = node["parameters"]["jsCode"]
    # point it at the artifact field, keep content-safe mode (accents preserved)
    js = js.replace("const INPUT_FIELD  = 'text';", "const INPUT_FIELD  = 'artifact';")
    js = js.replace("const OUTPUT_FIELD = 'text';", "const OUTPUT_FIELD = 'artifact';")
    # ensure `items` is defined for the node's items.map(...) tail
    return "const items = $input.all();\n" + js


def dictionary_js():
    wf = json.load(open(DICT_WF, encoding="utf-8"))
    js = [n for n in wf["nodes"] if n["type"].endswith("code")][0]["parameters"]["jsCode"]
    marker = "// n8n Code node — process every incoming item"
    engine = js[:js.index(marker)]
    # never truncate our pages (default cap is 3,000 words; HTML artifacts exceed it)
    engine = engine.replace("const MAX_WORDS = 3000;", "const MAX_WORDS = 100000;")
    # robustness patch: the vendored replace-callback assumes exactly one capture
    # group (match, _p1, offset, whole); a rule whose regex has none shifts the
    # args and `whole` becomes undefined -> crash. Derive offset/whole from
    # `arguments` so it works for any group count. (Upstream bug; safe to re-apply.)
    engine = engine.replace(
        "out = out.replace(c.re, (match, _p1, offset, whole) => {",
        "out = out.replace(c.re, function (match) { var _a = arguments; "
        "var whole = _a[_a.length - 1]; var offset = _a[_a.length - 2];")
    wrapper = r"""
// --- WFP5 post-humanizer wrapper: swap surviving AI terms + MARK ---
const it = $input.first().json;
const art = String(it.artifact || '');
const r = humanize(art, '');
const detected = r.replacement_count > 0;
const sample = r.replacements.slice(0, 60).map(function (x) { return x.from + '→' + x.to; }).join('; ');
const deaiLog = detected
  ? ('AI terms detected & replaced via human-dictionary (no LLM): ' + r.replacement_count + ' swap(s). ' + sample)
  : 'No residual AI dictionary-terms detected.';
return [{ json: {
  recordId: it.recordId || '', baseId: it.baseId || '', tableId: it.tableId || '',
  ok: it.ok === true, error: it.error || '', artifact: r.text,
  signals: it.signals || '', factGuard: it.factGuard || '',
  aiDetected: detected, deaiLog: deaiLog
} }];
"""
    return engine + wrapper


def node(name, js, pos, nid):
    return {"parameters": {"jsCode": js}, "id": nid, "name": name,
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}


def main():
    wf = json.load(open(WF, encoding="utf-8"))
    nodes = {n["name"]: n for n in wf["nodes"]}

    norm = node("Normalize (no-LLM)", normalize_js(), [2000, 300], "post-normalize")
    dic = node("De-AI Dictionary (no-LLM)", dictionary_js(), [2180, 300], "post-dictionary")

    # make room: shift the tail right
    for nm in ("Output OK?", "Export to Drive", "Advance to Polishing", "Route to Needs Attention"):
        if nm in nodes:
            nodes[nm]["position"] = [nodes[nm]["position"][0] + 520, nodes[nm]["position"][1]]

    wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in ("Normalize (no-LLM)", "De-AI Dictionary (no-LLM)")]
    wf["nodes"].extend([norm, dic])

    c = wf["connections"]
    # Finalize now feeds Normalize -> Dictionary -> Output OK?
    c["Finalize (code)"] = {"main": [[{"node": "Normalize (no-LLM)", "type": "main", "index": 0}]]}
    c["Normalize (no-LLM)"] = {"main": [[{"node": "De-AI Dictionary (no-LLM)", "type": "main", "index": 0}]]}
    c["De-AI Dictionary (no-LLM)"] = {"main": [[{"node": "Output OK?", "type": "main", "index": 0}]]}

    # artifact now lives on the dictionary node; repoint the two readers
    for nm in ("Export to Drive", "Advance to Polishing"):
        s = json.dumps(nodes[nm]["parameters"])
        s = s.replace("$('Finalize (code)')", "$('De-AI Dictionary (no-LLM)')")
        nodes[nm]["parameters"] = json.loads(s)
    # mark: write the De-AI Log on advance
    adv = nodes["Advance to Polishing"]["parameters"]["columns"]["value"]
    adv["De-AI Log"] = "={{ $('De-AI Dictionary (no-LLM)').item.json.deaiLog }}"

    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    sz = os.path.getsize(WF)
    print(f"WFP5 post-humanizer added (Normalize -> De-AI Dictionary). WFP5 JSON now {sz//1024} KB.")

    pub = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not pub:
        print("no N8N key — wrote local JSON only.")
        return
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
