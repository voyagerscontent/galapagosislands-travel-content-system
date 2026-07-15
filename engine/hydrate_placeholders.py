#!/usr/bin/env python3
"""Hydrate {{TOKENS}} across the context-pack and n8n workflow from the SITE_CONFIG
BRAND BLOCK, so a redeploy is a single edit. Idempotent and reversible-ish (keeps a
.rendered copy; never overwrites the tokenized source unless --inplace).

Secrets: automation values (airtable_pat, n8n_api_key, etc.) are read from a
gitignored `.env` file at the repo root, which OVERRIDES SITE_CONFIG. This keeps
tokens out of git while SITE_CONFIG stays committable. See `.env.example`.

Usage:
  python engine/hydrate_placeholders.py            # writes *.rendered next to each file
  python engine/hydrate_placeholders.py --inplace  # replace tokens in-place (deploy)

Tokens resolved: {{BRAND}} {{BRAND_ALT}} {{DOMAIN}} {{TAGLINE}} {{PUBLISHER}}
{{PRIMARY_CTA}} {{CONTRIBUTORS}} plus automation values for the n8n workflow
({{airtable_base}} {{airtable_table}} {{airtable_pat}} {{n8n_base_url}}
{{n8n_intake_webhook}} {{n8n_api_key}}).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "SITE_CONFIG.md"
ENV = ROOT / ".env"

# .env KEY -> SITE_CONFIG automation key. Secrets live in .env (gitignored) and
# OVERRIDE anything in SITE_CONFIG, so no token is ever committed.
ENV_TO_CFG = {
    "AIRTABLE_PAT": "airtable_pat",
    "AIRTABLE_BASE": "airtable_base",
    "AIRTABLE_TABLE": "airtable_table",
    "N8N_BASE_URL": "n8n_base_url",
    "N8N_INTAKE_WEBHOOK": "n8n_intake_webhook",
    "N8N_API_KEY": "n8n_api_key",
}


def parse_env():
    """Read .env (if present) into a dict of SITE_CONFIG automation keys."""
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
    # contributors list -> comma string (empty => "brand editorial voice (no named contributor)")
    cm = re.search(r'CONTRIBUTORS:\s*\[(.*?)\]', text)
    contribs = ""
    if cm and cm.group(1).strip():
        contribs = ", ".join(s.strip().strip('"') for s in cm.group(1).split(",") if s.strip())
    vals["CONTRIBUTORS"] = contribs or "brand editorial voice (no named contributor)"
    # .env secrets override SITE_CONFIG (secrets never committed)
    vals.update(parse_env())
    return vals


def token_map(v):
    return {
        "{{BRAND}}": v.get("BRAND", ""),
        "{{BRAND_ALT}}": v.get("BRAND_ALT", ""),
        "{{DOMAIN}}": v.get("DOMAIN", ""),
        "{{TAGLINE}}": v.get("TAGLINE", ""),
        "{{PUBLISHER}}": v.get("PUBLISHER", ""),
        "{{PRIMARY_CTA}}": v.get("PRIMARY_CTA", ""),
        "{{CONTRIBUTORS}}": v.get("CONTRIBUTORS", ""),
        "{{airtable_base}}": v.get("airtable_base", ""),
        "{{airtable_table}}": v.get("airtable_table", ""),
        "{{airtable_pat}}": v.get("airtable_pat", ""),
        "{{n8n_base_url}}": v.get("n8n_base_url", ""),
        "{{n8n_intake_webhook}}": v.get("n8n_intake_webhook", ""),
        "{{n8n_api_key}}": v.get("n8n_api_key", ""),
    }


def main():
    inplace = "--inplace" in sys.argv
    vals = parse_brand_block()
    tokens = token_map(vals)
    targets = []
    for pat in ("context-pack/**/*.md", "context-pack/**/*.yaml",
                "engine/n8n_pipeline_corrected.json", "README.md", "INSTALL_PERPLEXITY.md"):
        targets += ROOT.glob(pat)
    n = 0
    for f in targets:
        if f.name == "SITE_CONFIG.md":
            continue
        s = f.read_text(encoding="utf-8")
        out = s
        for tok, val in tokens.items():
            out = out.replace(tok, val)
        if out != s:
            dest = f if inplace else f.with_suffix(f.suffix + ".rendered")
            dest.write_text(out, encoding="utf-8")
            n += 1
    print(f"hydrated {n} files ({'in place' if inplace else 'as *.rendered'}) "
          f"for BRAND={vals.get('BRAND','?')}")


if __name__ == "__main__":
    main()
