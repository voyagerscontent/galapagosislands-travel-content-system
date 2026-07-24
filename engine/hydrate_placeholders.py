#!/usr/bin/env python3
"""Hydrate {{TOKENS}} across the context-pack and n8n workflows from the SITE_CONFIG
BRAND BLOCK, so a redeploy is a single edit. Idempotent and reversible-ish.

Secrets: automation values (airtable_pat, n8n_api_key, pipeline_service_url, etc.)
are read from a gitignored `.env` file at the repo root, which OVERRIDES SITE_CONFIG.
This keeps secrets out of git while SITE_CONFIG stays committable.

Changelog v1.1:
  - Targets now include engine/n8n-production/WFP*.json so the production
    workflow JSONs are hydrated alongside the legacy n8n_pipeline_corrected.json.
  - Added PIPELINE_SERVICE_URL and PIPELINE_SERVICE_KEY tokens so the
    wire_pipeline_service.py values stay in one place.
  - Added GOOGLE_DRIVE_CREDENTIAL_ID token for WFP6/WFP7 Drive nodes.

Usage:
  python engine/hydrate_placeholders.py            # writes *.rendered next to each file
  python engine/hydrate_placeholders.py --inplace  # replace tokens in-place (deploy)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "SITE_CONFIG.md"
ENV = ROOT / ".env"

ENV_TO_CFG = {
    "AIRTABLE_PAT":              "airtable_pat",
    "AIRTABLE_BASE":             "airtable_base",
    "AIRTABLE_TABLE":            "airtable_table",
    "N8N_BASE_URL":              "n8n_base_url",
    "N8N_INTAKE_WEBHOOK":        "n8n_intake_webhook",
    "N8N_API_KEY":               "n8n_api_key",
    # v1.1 additions
    "PIPELINE_SERVICE_URL":      "pipeline_service_url",
    "PIPELINE_SERVICE_KEY":      "pipeline_service_key",
    "GOOGLE_DRIVE_CREDENTIAL_ID":"google_drive_credential_id",
}


def parse_env():
    vals = {}
    if not ENV.exists():
        return vals
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in ENV_TO_CFG and v:
            vals[ENV_TO_CFG[k]] = v
    return vals


def parse_brand_block():
    text = CFG.read_text(encoding="utf-8")
    vals = {}
    for m in re.finditer(r'^\s*([A-Za-z_]+):\s*"([^"]*)"', text, re.M):
        vals[m.group(1)] = m.group(2)
    for m in re.finditer(r'^\s*([A-Za-z_]+):\s*([^\s"#\[][^\n#]*?)\s*(?:#.*)?$', text, re.M):
        vals.setdefault(m.group(1), m.group(2).strip())
    cm = re.search(r'CONTRIBUTORS:\s*\[(.*?)\]', text)
    contribs = ""
    if cm and cm.group(1).strip():
        contribs = ", ".join(s.strip().strip('"') for s in cm.group(1).split(",") if s.strip())
    vals["CONTRIBUTORS"] = contribs or "brand editorial voice (no named contributor)"
    vals.update(parse_env())
    return vals


def token_map(v):
    return {
        "{{BRAND}}":                    v.get("BRAND", ""),
        "{{BRAND_ALT}}":                v.get("BRAND_ALT", ""),
        "{{DOMAIN}}":                   v.get("DOMAIN", ""),
        "{{TAGLINE}}":                  v.get("TAGLINE", ""),
        "{{PUBLISHER}}":                v.get("PUBLISHER", ""),
        "{{PRIMARY_CTA}}":              v.get("PRIMARY_CTA", ""),
        "{{CONTRIBUTORS}}":             v.get("CONTRIBUTORS", ""),
        "{{airtable_base}}":            v.get("airtable_base", ""),
        "{{airtable_table}}":           v.get("airtable_table", ""),
        "{{airtable_pat}}":             v.get("airtable_pat", ""),
        "{{n8n_base_url}}":             v.get("n8n_base_url", ""),
        "{{n8n_intake_webhook}}":       v.get("n8n_intake_webhook", ""),
        "{{n8n_api_key}}":              v.get("n8n_api_key", ""),
        # v1.1 additions
        "{{PIPELINE_SERVICE_URL}}":     v.get("pipeline_service_url", ""),
        "{{PIPELINE_SERVICE_KEY}}":     v.get("pipeline_service_key", ""),
        "{{GOOGLE_DRIVE_CREDENTIAL_ID}}": v.get("google_drive_credential_id", ""),
    }


def main():
    inplace = "--inplace" in sys.argv
    vals = parse_brand_block()
    tokens = token_map(vals)

    targets = []
    # v1.0 targets
    for pat in ("context-pack/**/*.md", "context-pack/**/*.yaml",
                "engine/n8n_pipeline_corrected.json", "README.md", "INSTALL_PERPLEXITY.md"):
        targets += ROOT.glob(pat)

    # v1.1: production WFP workflow JSONs
    wfp_dir = ROOT / "engine" / "n8n-production"
    if wfp_dir.exists():
        targets += list(wfp_dir.glob("WFP*.json"))
        targets += list(wfp_dir.glob("WFPD*.json"))

    n = 0
    for f in targets:
        if f.name == "SITE_CONFIG.md":
            continue
        try:
            s = f.read_text(encoding="utf-8")
        except Exception:
            continue
        out = s
        for tok, val in tokens.items():
            out = out.replace(tok, val)
        if out != s:
            dest = f if inplace else f.with_suffix(f.suffix + ".rendered")
            dest.write_text(out, encoding="utf-8")
            n += 1

    hydrated_wfp = sum(1 for f in targets if f.suffix == ".json" and "WFP" in f.name)
    print(f"hydrated {n} files ({'in place' if inplace else 'as *.rendered'}) "
          f"for BRAND={vals.get('BRAND','?')} "
          f"(includes {hydrated_wfp} WFP workflow JSONs)")

    # Warn about missing secrets
    for key, cfg_key in ENV_TO_CFG.items():
        if not vals.get(cfg_key):
            print(f"  WARN: {key} not set in .env — {{{{{'{'}{cfg_key}{'}'}}}}} left unreplaced")


if __name__ == "__main__":
    main()
