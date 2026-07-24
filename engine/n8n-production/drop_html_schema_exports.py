#!/usr/bin/env python3
"""Editor-doc-only: drop the standalone HTML page + JSON-LD schema file exports from WFP6.

Per the owner: "you only need to produce the editor doc — no need for the html page or
json schema page." The polished markup is still produced internally (the QA gate at WFP7
and the editor-doc render still consume it); only the two extra Drive deliverables go.

Rewires:  Export editor Doc -> Export HTML -> Export JSON-LD -> Notify
   to:     Export editor Doc -> Notify
and deletes the Export HTML / Export JSON-LD nodes.
"""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP6_polish.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "U0MrpTN3hv4RfNMI"
DROP = ("Export HTML", "Export JSON-LD")


def main():
    wf = json.load(open(WF, encoding="utf-8"))
    present = [n["name"] for n in wf["nodes"]]
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in DROP]
    for nm in DROP:
        wf["connections"].pop(nm, None)
    # editor doc now flows straight to Notify webmasters (the next real node)
    wf["connections"]["Export editor Doc"] = {"main": [[{"node": "Notify webmasters", "type": "main", "index": 0}]]}

    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("dropped:", [d for d in DROP if d in present], "| editor Doc -> Notify webmasters")

    pub = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not pub:
        print("no key — local only."); return
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
