#!/usr/bin/env python3
"""
Generate an importable n8n workflow JSON for the pattern-breaker service.

The workflow is intentionally thin: n8n only orchestrates HTTP calls to the
FastAPI service (/detect and /process). All logic — deterministic detection AND
the guarded Claude restructure — lives in the service, so this same workflow can
be dropped into ANY n8n instance or repo just by changing the base URL.

Two entry points are produced:
  - Webhook trigger  -> POST text in, get processed result out (for apps/APIs).
  - Manual trigger   -> for quick testing inside the n8n editor.

Usage:
    python3 n8n/build_n8n_workflow.py            # writes n8n_workflow_http.json
    PB_SERVICE_URL=https://pb.example.com python3 n8n/build_n8n_workflow.py
"""

import json
import os
from pathlib import Path

SERVICE_URL = os.environ.get("PB_SERVICE_URL", "http://pattern-breaker:8080")
OUT = Path(__file__).resolve().parent / "n8n_workflow_http.json"


def build() -> dict:
    return {
        "name": "Pattern Breaker — Detect & Restructure",
        "nodes": [
            {
                "parameters": {},
                "id": "manual-trigger",
                "name": "Manual Trigger (test)",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [240, 160],
            },
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "pattern-breaker",
                    "responseMode": "lastNode",
                    "options": {},
                },
                "id": "webhook-trigger",
                "name": "Webhook (POST text)",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [240, 360],
                "webhookId": "pattern-breaker",
            },
            {
                "parameters": {
                    "jsCode": (
                        "// Normalise input from either trigger into { text }\n"
                        "const item = $input.first().json;\n"
                        "const text = item.body?.text ?? item.text ?? "
                        "'The islands offer a unique experience. The islands "
                        "provide stunning views. The islands deliver great "
                        "moments. The islands create memories.';\n"
                        "return [{ json: { text } }];"
                    )
                },
                "id": "prep",
                "name": "Prep Input",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [500, 260],
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": f"{SERVICE_URL}/process",
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": "={{ JSON.stringify({ text: $json.text }) }}",
                    "options": {"timeout": 120000},
                },
                "id": "process",
                "name": "POST /process",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [760, 260],
                "notes": "Full 2-phase run. For detection-only, change URL to /detect.",
            },
            {
                "parameters": {
                    "jsCode": (
                        "// Shape a tidy result for downstream nodes.\n"
                        "const r = $input.first().json;\n"
                        "return [{ json: {\n"
                        "  changed: r.changed,\n"
                        "  flags_cleared: r.flags_cleared,\n"
                        "  needs_human_review: r.needs_human_review,\n"
                        "  factors_before: [...new Set((r.phase1?.flags||[])"
                        ".map(f=>f.factor))],\n"
                        "  final_text: r.final_text,\n"
                        "  final_html: r.final_html\n"
                        "} }];"
                    )
                },
                "id": "shape",
                "name": "Shape Result",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [1020, 260],
            },
        ],
        "connections": {
            "Manual Trigger (test)": {"main": [[{"node": "Prep Input", "type": "main", "index": 0}]]},
            "Webhook (POST text)": {"main": [[{"node": "Prep Input", "type": "main", "index": 0}]]},
            "Prep Input": {"main": [[{"node": "POST /process", "type": "main", "index": 0}]]},
            "POST /process": {"main": [[{"node": "Shape Result", "type": "main", "index": 0}]]},
        },
        "active": False,
        "settings": {"executionOrder": "v1"},
        "meta": {
            "templateCredsSetupCompleted": True,
            "description": (
                "Calls the Pattern Breaker FastAPI service. Change SERVICE_URL "
                "at build time or edit the HTTP node's URL. If PB_API_TOKEN is "
                "set on the service, add an 'Authorization: Bearer <token>' "
                "header to the HTTP Request node."
            ),
        },
        "pinData": {},
    }


if __name__ == "__main__":
    wf = build()
    OUT.write_text(json.dumps(wf, indent=2), encoding="utf-8")
    print(f"wrote {OUT} (service URL: {SERVICE_URL})")
