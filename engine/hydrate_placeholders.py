#!/usr/bin/env python3
"""Hydrate {{TOKENS}} across the context-pack and n8n workflow from the SITE_CONFIG
BRAND BLOCK, so a redeploy is a single edit. Idempotent and reversible-ish (keeps a
.rendered copy; never overwrites the tokenized source unless --inplace).

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
