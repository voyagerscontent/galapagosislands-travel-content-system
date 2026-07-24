# Pattern Breaker — Native n8n workflow

Runs the entire two-phase system **inside n8n** with no external server. Phase 1
(the deterministic detector) runs in a Code node as JavaScript; Phase 2 calls
Claude Sonnet via an HTTP Request node using your existing Anthropic credential.

## Files
- `n8n_workflow_native.json` — the importable workflow (this is what's deployed).
- `phase1_detector.js` — Phase 1 detector, JavaScript port of `detector/detector.py`.
  **Parity-verified**: byte-identical metrics, factors, flag counts and span
  offsets vs. the Python detector on both AI and human samples.
- `prepare_spans.js` — builds one Claude payload per flagged span (hardcoded
  system prompt + user template + deterministic Markov cadence seeds + shape).
- `guard_and_stitch.js` — deterministic fact-guard (port of `factguard.py`),
  light-blue review highlighting, and span stitching.
- `build_native_workflow.py` — regenerates `n8n_workflow_native.json` from the
  three `.js` files (single source of truth).

## Flow
```
Webhook (POST /webhook/pattern-breaker)
  -> Phase 1 Detect (Code, deterministic, no LLM)
  -> Prepare Spans (Code, one item per flagged span; passthrough if clean)
  -> Claude Sonnet (HTTP Request, per span, reuses "Anthropic API (x-api-key)")
  -> Guard & Stitch (Code, fact-guard + highlight + stitch, runOnce)
  -> Respond (JSON)
```

## Deployed instance
- Instance: `https://voyagerscontent.app.n8n.cloud`
- Workflow ID: `2ToiqCivCTCj74oK`
- Name: **Pattern Breaker (native, 2-phase deterministic)**
- Webhook: `POST https://voyagerscontent.app.n8n.cloud/webhook/pattern-breaker`

## Call it
```bash
curl -s -X POST https://voyagerscontent.app.n8n.cloud/webhook/pattern-breaker \
  -H "content-type: application/json" \
  -d '{"text":"<your content here>"}'
```

Response:
```json
{
  "changed": true,
  "needs_human_review": false,
  "output_text": "...restructured text with [[PB-REVIEW]] markers on flagged spans...",
  "output_html": "...same, with light-blue <span> highlights...",
  "span_results": [ ... per-span guard details ... ],
  "summary": { "spans_total": 3, "spans_accepted": 3, "spans_flagged_for_review": 0 }
}
```
Clean text returns `changed:false` and the original untouched.

## Anthropic credential
The Claude node uses the existing n8n credential **"Anthropic API (x-api-key)"**
(`httpHeaderAuth`, id `yiT1TUHmUx7Eklbv`) — the same one your other Weboptimizer
workflows use. No key is stored in the workflow JSON.

Model is `claude-sonnet-4-6` (set in `prepare_spans.js`; override via an n8n
variable `PB_CLAUDE_MODEL`).

## Intentional differences from the Python reference
1. **Markov corpus**: the Python engine also trains on
   `dictionary/human_corpus.json` (2,307 human travel sentences). The native node
   trains on the **span's own text only** — inlining 100 KB into a Code node is
   impractical, and the seeds are rhythm inspiration only. The deterministic
   fact-guard still rejects any new number/entity regardless, so safety is
   unchanged.
2. **Single pass**: the Python `pipeline.py` re-verifies and can re-run Phase 2
   up to 3 times to squeeze residual flags. The native workflow does one Phase-2
   pass. In testing this cleared 4 of 5 factors (burstiness 0.12 -> 0.44,
   CV 0.14 -> 0.79). To iterate, wire the `Respond` output back through a second
   Detect -> Prepare -> Claude loop, or call the webhook again on the output.

## Regenerate / re-import
```bash
python3 n8n/build_native_workflow.py      # rebuilds n8n_workflow_native.json
```
Then import via the n8n UI, or update the live workflow via the API
(`PUT /api/v1/workflows/2ToiqCivCTCj74oK`).
