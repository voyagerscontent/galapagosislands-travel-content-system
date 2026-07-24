# Auto-deploy: GitHub -> n8n (GitHub is the source of truth)

Every push to `main` that touches `n8n/**` redeploys the live workflow in n8n
cloud, so the running workflow is always the latest version in this repo. You can
also trigger it manually from the Actions tab ("Run workflow").

## How it works
1. `.github/workflows/deploy-n8n.yml` runs on push to `main` (path-filtered to
   `n8n/**`) and on manual dispatch.
2. It runs `n8n/deploy_to_n8n.py`, which:
   - regenerates `n8n_workflow_native.json` from the `.js` source files
     (`phase1_detector.js`, `prepare_spans.js`, `guard_and_stitch.js`),
   - `PUT`-updates the **existing** workflow (never creates a duplicate),
   - re-activates it so the webhook stays live.

## One-time setup (required for the Action to run)
In the repo: **Settings -> Secrets and variables -> Actions**

Add a **secret**:
| Name | Value |
| :--- | :---- |
| `N8N_API_KEY` | an n8n public API key (n8n cloud -> Settings -> n8n API -> Create API key) |

Add **variables** (optional; sensible defaults are baked in):
| Name | Default if unset |
| :--- | :--------------- |
| `N8N_BASE_URL` | `https://voyagerscontent.app.n8n.cloud` |
| `N8N_WORKFLOW_ID` | `2ToiqCivCTCj74oK` |

That's it. After the secret is set, edit any file under `n8n/`, push to `main`,
and the live workflow updates automatically.

## Deploy manually from your machine
```bash
export N8N_BASE_URL="https://voyagerscontent.app.n8n.cloud"
export N8N_API_KEY="<your n8n api key>"
export N8N_WORKFLOW_ID="2ToiqCivCTCj74oK"
python3 n8n/deploy_to_n8n.py
```

## Notes
- The workflow's Anthropic credential ("Anthropic API (x-api-key)") is referenced
  by id and lives in n8n, not in the repo — deploys never touch it.
- The n8n API key is a stored GitHub secret; it is never printed in logs.
- If you rename the workflow or want a different target, change `N8N_WORKFLOW_ID`.
