#!/usr/bin/env python3
"""WFP3: feed the burstiness gate's failure back into the re-draft prompt.

When WFP5's burstiness gate fails a page (<3 retries) it loops back to Drafting and
writes an instructional string to the "Burstiness Feedback" record field (see
add_burstiness_gate.py). This applier appends a conditional block to the WFP3 draft
agent's prompt so that string is injected ONLY on a retry — a normal first draft has
the field empty and the block renders to nothing.

The draft agent's message content is already one big n8n expression (starts with '=',
interpolates {{ $json['Field'] }} from the claimed record). We append one more {{ }}
block at the tail; idempotent via a marker string.

Run:  N8N_API_KEY=... python engine/n8n-production/add_draft_burstiness_feedback.py
"""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP3_draft.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "eExgOTVFIoCuJb0D"
MARKER = "BURSTINESS RETRY FEEDBACK"

# Leading real newlines separate it from the prior literal text; the \\n inside the
# ternary are backslash-n in the stored JS source (n8n renders them as newlines).
BLOCK = ("\n\n{{ $json['Burstiness Feedback'] ? '=== " + MARKER +
         " (HIGHEST PRIORITY — your last draft was rejected for flat rhythm) ==="
         "\\n' + $json['Burstiness Feedback'] + '\\n=== end feedback ===' : '' }}")


def main():
    wf = json.load(open(WF, encoding="utf-8"))
    agent = next(n for n in wf["nodes"] if n["name"] == "Run Stage Agent")
    msg = agent["parameters"]["messages"]["values"][0]
    if MARKER in msg["content"]:
        print("feedback block already present — nothing to append (idempotent).")
    else:
        msg["content"] = msg["content"] + BLOCK
        json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"WFP3: appended burstiness-feedback block to draft prompt. {os.path.getsize(WF)//1024} KB")

    key = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not key:
        print("no key — local only."); return
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})}
    req = urllib.request.Request(N8N + "/api/v1/workflows/" + WID, data=json.dumps(body).encode(),
                                 headers={"X-N8N-API-KEY": key, "Content-Type": "application/json"}, method="PUT")
    try:
        d = json.load(urllib.request.urlopen(req))
        print("pushed to n8n:", "ok" if d.get("id") else "??", "| active:", d.get("active"))
    except urllib.error.HTTPError as e:
        print("push ERR %d %s" % (e.code, e.read().decode()[:300]))


if __name__ == "__main__":
    main()
