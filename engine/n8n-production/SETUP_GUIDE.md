# n8n Pipeline — Go-Live Setup Guide
**GalapagosIslands.travel Content Production System**
Last updated: July 2026

---

## What this guide covers
Five steps to run the full autonomous pipeline from Airtable Backlog → polished HTML in Google Drive:
1. Generate your n8n API key (lets us query execution logs remotely)
2. Add the Google Drive OAuth credential in n8n
3. Update WFP6 + WFP7 with the real Drive credential ID
4. Import the updated workflow JSONs
5. Fire a hardcoded test run on Bartolomé Island

Total time: ~15 minutes.

---

## STEP 1 — Generate n8n API Key

**Why:** Lets this agent query execution history and confirm Anthropic calls succeed without you logging in manually.

1. Go to → **https://voyagerscontent.app.n8n.cloud**
2. Log in
3. Bottom-left corner → click your **avatar/name**
4. Click **Settings**
5. Left sidebar → **API**
6. Click **Create API Key**
7. Name it: `Computer Agent`
8. Copy the key (it starts with `n8n_api_...`)
9. Paste it here in chat — I'll store it as a credential so I can query execution logs going forward

---

## STEP 2 — Add Google Drive OAuth Credential in n8n

**Why:** WFP6 and WFP7 now have Drive write nodes, but they reference a credential called `Google Drive — Content Engine`. You need to create it.

1. In n8n → left sidebar → **Credentials**
2. Click **+ Add Credential**
3. Search for **Google Drive OAuth2 API**
4. Click it → a form opens
5. Name it exactly: `Google Drive — Content Engine`
6. Click **Sign in with Google**
7. Choose the Google account that owns the Drive folder `1_Tliljbgdl0HBqBcBfrtd6CPHMdOmtaE`
8. **Grant these permissions when prompted:**
   - ✅ See, edit, create, and delete all your Google Drive files
   - ✅ See and download all your Google Drive files
9. Click **Save** — n8n shows the credential with an ID like `abc123def456`
10. **Copy that credential ID** — you'll need it in Step 3

---

## STEP 3 — Update Credential ID in WFP6 + WFP7

The workflow JSONs have `{{GOOGLE_DRIVE_CREDENTIAL_ID}}` as a placeholder. Replace it with the real ID from Step 2.

**Option A — Do it in n8n UI (easiest):**
1. Open **WFP6 Polishing (Drive-enabled)**
2. Click the **Write to Google Drive** node
3. In the Credentials dropdown → select **Google Drive — Content Engine**
4. Save the workflow
5. Repeat for **WFP7 Auditor Review (Drive-enabled)** → **Write Audit Report to Drive** node

**Option B — Tell me the credential ID:**
Paste the ID from Step 2 into chat (format: `abc123def456`) and I'll patch both JSONs and push them to the repo automatically.

---

## STEP 4 — Import Updated Workflow JSONs

The updated WFP6 and WFP7 are in the GitHub repo at:
```
engine/n8n-production/WFP6_polish.json
engine/n8n-production/WFP7_auditor.json
```

**To import into n8n:**
1. In n8n → **Workflows** list
2. Find **WFP6 Polishing** → click the three-dot menu → **Import from file** → select `WFP6_polish.json`
   - OR: open the workflow → top-right menu → **Import** → paste the JSON
3. Repeat for **WFP7 Auditor Review**
4. Make sure both show the new **Write to Google Drive** node in the canvas
5. **Activate** both workflows (toggle on)

---

## STEP 5 — Verify All 8 Workflows Are Active

In n8n Workflows list, confirm these all show the green **Active** toggle:

| Workflow | Webhook path |
|---|---|
| WFP0 Production Intake | `/webhook/galapagos-production/stage/intake` |
| WFP1 Scoring | `/webhook/galapagos-production/stage/scoring` |
| WFP2 Brief Ready | `/webhook/galapagos-production/stage/brief` |
| WFP3 Drafting | `/webhook/galapagos-production/stage/draft` |
| WFP4 Truth Check | `/webhook/galapagos-production/stage/truthcheck` |
| WFP5 Humanizing | `/webhook/galapagos-production/stage/humanize` |
| WFP6 Polishing (Drive-enabled) | `/webhook/galapagos-production/stage/polish` |
| WFP7 Auditor Review (Drive-enabled) | `/webhook/galapagos-production/stage/auditor` |

> WFP0 and WFP1 are already active (confirmed July 16). The others may still be inactive — check and toggle them on.

---

## STEP 6 — Get a Real Airtable Record ID

**Why:** The test run needs an actual Airtable record at `Backlog` status.

1. Go to your Airtable base: `appNkUL50eF601ejN`
2. Open table `tblUgxSGGfeJIL5GD` (Content Production — GalapagosIslands.travel)
3. Find the **Bartolomé Island** row
4. The URL will show `rec` + 14 characters — that's the record ID (e.g. `recABCDEFGHIJKL`)
5. Make sure the Status field is set to **Backlog**
6. Paste the record ID here

---

## STEP 7 — Fire the Test Run

Once you give me the record ID, I'll POST this to the intake webhook:

```bash
curl -X POST \
  "https://voyagerscontent.app.n8n.cloud/webhook/galapagos-production/stage/intake" \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "galapagosislands-travel-v1",
    "record_id": "recXXXXXXXXXXXXXX"
  }'
```

Expected behavior:
- WFP0 receives it → sets status to `Scoring` → chains to WFP1
- WFP1 calls Anthropic (scoring) → sets to `Brief Ready` → chains to WFP2
- WFP2 calls Anthropic (brief) → sets to `Drafting` → chains to WFP3
- ... continues through WFP6 which now also writes the HTML to Drive folder
- WFP7 runs audit → sets to `Editor Review` → stops (human gate)
- Drive folder `07 Polished for Editor` receives the HTML file

Full chain takes ~8–12 minutes depending on Anthropic response times.

---

## What each stage writes to Airtable

| Stage | Airtable field written |
|---|---|
| WFP1 Scoring | ROI Score |
| WFP2 Brief | Brief Content |
| WFP3 Draft | Draft Content |
| WFP4 Truth Check | (gate only — routes to Humanizing or Needs Attention) |
| WFP5 Humanize | Humanized Content |
| WFP6 Polish | Polished Content + writes HTML to Drive |
| WFP7 Auditor | Auditor Result + writes audit report to Drive |

---

## What Drive gets

After WFP6 runs, the folder `1jf8kwaFmFHpYTgmLYSVSMU4yq-YBM5bH` (07 Polished for Editor) will contain:

- `Bartolomé Island — Polished.html` — the full production HTML, self-contained, CMS-ready
- `Bartolomé Island — Audit Report.txt` — WFP7 Parts A–G results

The docx continues to be produced separately (manually via this agent or future docx node).

---

## Summary of what I still need from you

| Item | How to get it |
|---|---|
| **n8n API key** | Settings → API → Create API Key |
| **Google Drive credential ID** | After you create it in n8n (Step 2) |
| **Bartolomé Airtable record ID** | Airtable base `appNkUL50eF601ejN`, Bartolomé row URL |

Once I have these three things, I can patch the workflows and fire the test run in one shot.
