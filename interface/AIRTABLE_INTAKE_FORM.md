# Team Intake Interface — two ways to activate the pipeline

Anyone on the team can launch a page by **adding data**. Submitting creates an Airtable record with `Status = Backlog`; the n8n poll picks it up and runs the sequence. Both options below capture the same fields, including the **optional human-enrichment** add-ons.

---
## Option A — Native Airtable (no hosting) — "trigger at Airtable"
Use Airtable's built-in **Form view** or **Interface**.

1. In the Pages Master table, add the intake fields from `airtable_intake_fields.json` (see below).
2. Create a **Form view** named "New Page Request". Add fields in this order; mark the required ones:
   - Page Title* · Target URL · Page Type* (single select) · Topic* (long text)
   - Persona* (single select) · Funnel Stage* (single select) · Primary CTA (default "Talk to a Galápagos Specialist") · Priority
   - **Human Paragraphs · Human Quotes · Anecdotes · Contributor** (all optional)
   - Set a hidden default: **Status = Backlog** (Form views can default it, or an automation sets it on create).
3. Share the form link with the team. Each submit = one Backlog record = pipeline activates.
4. (Optional) An Airtable **Automation** "When record created → set Status = Backlog, stamp Created By" guarantees the trigger field.

This is the zero-infrastructure path: the form *is* the trigger.

---
## Option B — Hosted web form (online) — `intake-form.html`
For teammates who shouldn't have Airtable access, host `intake-form.html` (Netlify / Vercel / GitHub Pages / S3).

It POSTs the form as JSON to a webhook that creates the Airtable record **server-side** (so no token is exposed in the browser):

1. In n8n, add a **Webhook** node (path e.g. `git-intake`) → **Airtable: Create Record** node mapping the JSON fields → set `Status = Backlog`.
2. Put that webhook URL into `intake-form.html` as `WEBHOOK_URL`.
3. Host the file. Done — submissions flow straight into Backlog.

> Make/Zapier work identically (Webhook → Airtable Create). Avoid putting an Airtable PAT in client-side JS.

---
## Fields created (add to Pages Master)
See `airtable_intake_fields.json`. Summary:

| Field | Type | Required | Purpose |
|---|---|---|---|
| Page Title | Single line | yes | record name |
| Target URL | Single line | no | slug |
| Page Type | Single select | yes | hub / vessel profile / comparison / guide / FAQ |
| Topic | Long text | yes | what the page answers |
| Persona | Single select | yes | sub-step A input |
| Funnel Stage | Single select | yes | awareness / consideration / decision |
| Primary CTA | Single line | no | default lead CTA |
| Priority | Single select | no | scheduling |
| **Human Paragraphs** | Long text | no | verbatim human prose add-on |
| **Human Quotes** | Long text | no | one per line + attribution |
| **Anecdotes** | Long text | no | true stories |
| **Contributor** | Single line | no | attribution name |
| Created By | Collaborator/Created-by | auto | who launched it |

These are **additive** Airtable fields — they do not touch the 12 `Status` values, so the engine contract and `validate_pipeline.py` are unaffected.

## How enrichment flows through the pipeline
The four enrichment fields are read at **Drafting** (sub-step 4b in `CONTENT_GENERATION_PROMPT.md`): the writer places human paragraphs/quotes/anecdotes **verbatim and attributed**, fits them lightly into the page, and never paraphrases them. The **Guardian of Truth** treats them as human-attributed (exempt from source-of-truth citation, but they must not contradict MASTER_FACTS). The **Auditor** confirms they were preserved and attributed. If all four are empty, the page is produced normally — they are optional.
