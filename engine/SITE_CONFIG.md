# SITE_CONFIG

The only values that change per site. The pipeline (status model, orchestrator, schema, workflow) stays identical. Plain ASCII status values keep n8n + Airtable + Perplexity byte-for-byte aligned.

## oceanalbatros.com (reference — filled)
```
site_name: oceanalbatros.com
site_id: oceanalbatros-com-v1
operator: Polar Latitudes Expeditions
gsa: Latin Trails
default_voice: Marcel Perkins (CEO & MD, Latin Trails)
airtable_base: appNkUL50eF601ejN
airtable_table: tblUgxSGGfeJIL5GD
airtable_credential_name: Airtable API - oceanalbatros.com
n8n_poll_minutes: 5
status_field: Status
status_values: [Backlog, Scoring, Brief Ready, Drafting, Truth Check, Humanizing, Polishing, Auditor Review, Editor Review, Ready to Publish, Published, Needs Attention]
hard_entity_rules:
  - latin_trails: GSA only; never operator/owner/charterer/cruise line
  - polar_latitudes: sole operator citation
  - chimu_adventures: never named publicly
  - marcel_perkins: CEO & MD, Latin Trails - main editorial voice
```

## New-site fork template (fill in, keep status_values identical)
```
site_name: [SITE NAME]
site_id: [your-site-slug-v1]
operator: [OPERATOR LEGAL NAME]
gsa: [GSA LEGAL NAME - usually Latin Trails]
default_voice: [WRITER NAME AND TITLE]
airtable_base: [appXXXX - create new base]
airtable_table: [tblXXXX - Pages Master]
airtable_credential_name: Airtable API - [SITE NAME]
n8n_poll_minutes: 5
status_field: Status
status_values: [Backlog, Scoring, Brief Ready, Drafting, Truth Check, Humanizing, Polishing, Auditor Review, Editor Review, Ready to Publish, Published, Needs Attention]
hard_entity_rules: [GSA vs operator vs owner; locked titles; never-cited sisters]
```

> Do not change `status_values` when forking. They are the contract shared by Airtable, the 5 n8n workflows, the Perplexity orchestrator, and the Auditor. Changing one without the others is what causes stalls and loops.
