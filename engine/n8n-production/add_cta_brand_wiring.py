#!/usr/bin/env python3
"""WFP6: honor the per-page 'CTA Brand' field when the polish agent writes the CTA.

The polish prompt's default is a dual CTA by audience — Voyagers Travel as the primary
consumer CTA (https://www.voyagers.travel/galapagos) and Latin Trails as a secondary
trade aside (https://www.latintrails.com). The intake form now sets a per-page 'CTA Brand'
choice; this applier makes that choice authoritative by injecting a directive that pins the
PRIMARY CTA to the selected brand+URL. Empty (pages not produced via the form) defaults to
Voyagers Travel, preserving current behavior.

Inserted just before the "HUMANIZED:" block so it reads as a final instruction, not content.
Deterministic brand->URL mapping (no reliance on the model remembering URLs). Idempotent.

Run:  N8N_API_KEY=... python engine/n8n-production/add_cta_brand_wiring.py
"""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP6_polish.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "U0MrpTN3hv4RfNMI"
MARKER = "CTA BRAND — per-page"
ANCHOR = "\n\nHUMANIZED:"

DIRECTIVE = (
    "\n\nCTA BRAND — per-page, AUTHORITATIVE (overrides the audience-split default above): "
    "{{ $json['CTA Brand'] || 'Voyagers Travel' }}. The PRIMARY call-to-action on this page MUST use "
    "{{ $json['CTA Brand'] === 'Latin Trails' ? 'Latin Trails → https://www.latintrails.com' "
    ": 'Voyagers Travel → https://www.voyagers.travel/galapagos' }}. "
    "Use ONLY this brand and URL for the PRIMARY CTA — do not substitute the other brand for the primary. "
    "The non-selected brand may appear at most as a minor secondary aside if editorially natural."
)


def api(path, method="GET", body=None, key=None):
    req = urllib.request.Request(N8N + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-N8N-API-KEY": key, "Content-Type": "application/json"}, method=method)
    return json.load(urllib.request.urlopen(req))


def main():
    key = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not key:
        print("no key — cannot fetch/push."); return
    wf = api(f"/api/v1/workflows/{WID}", key=key)          # operate on live to avoid drift
    agent = next(n for n in wf["nodes"] if n["name"] == "Run Stage Agent")
    msg = agent["parameters"]["messages"]["values"][0]
    c = msg["content"]
    if MARKER in c:
        print("CTA-brand directive already present — idempotent, re-pushing anyway.")
    else:
        if ANCHOR not in c:
            raise SystemExit("Anchor '\\n\\nHUMANIZED:' not found — polish prompt changed; update ANCHOR.")
        c = c.replace(ANCHOR, DIRECTIVE + ANCHOR, 1)
        msg["content"] = c
        print("injected CTA-brand directive before HUMANIZED block.")

    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})}
    api(f"/api/v1/workflows/{WID}", "PUT", body, key)
    # keep the repo copy in sync with what we just pushed
    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("pushed to n8n + saved local WFP6_polish.json. prompt now", len(c), "chars.")


if __name__ == "__main__":
    main()
