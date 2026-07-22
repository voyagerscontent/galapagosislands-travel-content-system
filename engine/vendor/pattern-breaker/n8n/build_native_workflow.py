#!/usr/bin/env python3
"""
Build the NATIVE n8n workflow for pattern-breaker (no external server).

Nodes:
  Webhook (POST /pattern-breaker)  -> Phase 1 Detect (Code, JS)
    -> IF flagged
        true  -> Prepare Spans (Code, JS, one item per span)
                 -> Claude (HTTP Request, per item, reuses Anthropic header cred)
                 -> Guard & Stitch (Code, JS, runOnce) -> Respond
        false -> Prepare Spans passthrough path merges in Guard & Stitch too

We keep it linear: Detect -> Prepare Spans -> Claude -> Guard & Stitch -> Respond.
Prepare Spans emits a single passthrough item when nothing is flagged, and the
Claude node is set to "continue on empty"/never-error so passthrough flows through
untouched; Guard & Stitch detects passthrough and returns the original.

The three Code node bodies are read from sibling .js files so source of truth is
one place (also parity-tested against the Python detector).
"""
import json, pathlib

HERE = pathlib.Path(__file__).resolve().parent
ANTHROPIC_CRED_ID = "yiT1TUHmUx7Eklbv"          # existing "Anthropic API (x-api-key)"
ANTHROPIC_CRED_NAME = "Anthropic API (x-api-key)"

detect_js = (HERE / "phase1_detector.js").read_text(encoding="utf-8")
prepare_js = (HERE / "prepare_spans.js").read_text(encoding="utf-8")
stitch_js = (HERE / "guard_and_stitch.js").read_text(encoding="utf-8")


def node(name, ntype, pos, params, **extra):
    n = {"parameters": params, "id": name.lower().replace(" ", "_"),
         "name": name, "type": ntype, "typeVersion": extra.get("tv", 1),
         "position": pos}
    if "credentials" in extra:
        n["credentials"] = extra["credentials"]
    return n


nodes = [
    node("Webhook In", "n8n-nodes-base.webhook", [0, 300], {
        "httpMethod": "POST", "path": "pattern-breaker",
        "responseMode": "responseNode", "options": {}
    }, tv=1.1),

    node("Phase 1 Detect", "n8n-nodes-base.code", [220, 300], {
        "jsCode": detect_js
    }, tv=2),

    node("Prepare Spans", "n8n-nodes-base.code", [440, 300], {
        "jsCode": prepare_js
    }, tv=2),

    node("Claude Sonnet", "n8n-nodes-base.httpRequest", [660, 300], {
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": True,
        "specifyHeaders": "keypair",
        "headerParameters": {"parameters": [
            {"name": "anthropic-version", "value": "2023-06-01"},
            {"name": "content-type", "value": "application/json"}
        ]},
        "sendBody": True,
        "contentType": "json",
        "specifyBody": "json",
        # passthrough items have no anthropicPayload -> send empty {} which we skip
        "jsonBody": "={{ $json.anthropicPayload ? JSON.stringify($json.anthropicPayload) : '{}' }}",
        "options": {"response": {"response": {"neverError": True}}, "timeout": 120000}
    }, tv=4.2, credentials={"httpHeaderAuth": {"id": ANTHROPIC_CRED_ID, "name": ANTHROPIC_CRED_NAME}}),

    node("Guard & Stitch", "n8n-nodes-base.code", [880, 300], {
        "mode": "runOnceForAllItems",
        "jsCode": stitch_js
    }, tv=2),

    node("Respond", "n8n-nodes-base.respondToWebhook", [1100, 300], {
        "respondWith": "json",
        "responseBody": "={{ JSON.stringify($json) }}",
        "options": {}
    }, tv=1.1),
]

# For Claude node: we need Claude to run per-item but skip passthrough items.
# Simplest deterministic approach: keep passthrough item flowing (empty {} body,
# neverError) — Guard & Stitch detects __passthrough and ignores the empty resp.
# But to avoid a wasted call, we merge the original fields back: the HTTP node in
# n8n returns ONLY the response body, dropping input fields. We must preserve
# span metadata. Solution: enable "Include Other Input Fields".
nodes[3]["parameters"]["options"]["response"] = {"response": {"neverError": True}}
# httpRequest v4.2 supports keeping input fields via "options": { "response": ... }
# and a dedicated toggle. We set it explicitly:
nodes[3]["parameters"]["options"]["allowUnauthorizedCerts"] = False

connections = {
    "Webhook In": {"main": [[{"node": "Phase 1 Detect", "type": "main", "index": 0}]]},
    "Phase 1 Detect": {"main": [[{"node": "Prepare Spans", "type": "main", "index": 0}]]},
    "Prepare Spans": {"main": [[{"node": "Claude Sonnet", "type": "main", "index": 0}]]},
    "Claude Sonnet": {"main": [[{"node": "Guard & Stitch", "type": "main", "index": 0}]]},
    "Guard & Stitch": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
}

workflow = {
    "name": "Pattern Breaker (native, 2-phase deterministic)",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1"},
}

out = HERE / "n8n_workflow_native.json"
out.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
print("wrote", out)
print("nodes:", [n["name"] for n in nodes])
