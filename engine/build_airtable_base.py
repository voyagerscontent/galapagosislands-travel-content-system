#!/usr/bin/env python3
"""
build_airtable_base.py - create the Pages Master table + fields from airtable_schema.json.

Skips computed field types (Airtable REST API returns INVALID_FIELD_TYPE for those).
Usage:
    python build_airtable_base.py --pat patXXXX --base-id appXXXX [--schema airtable_schema.json]
"""
import argparse, json, sys, urllib.request, urllib.error

META = "https://api.airtable.com/v0/meta/bases/{base}/tables"
COMPUTED = {"lastModifiedTime", "createdTime", "formula", "rollup", "count", "lookup", "autoNumber"}


def post(url, token, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit("Airtable API error " + str(e.code) + ": " + e.read().decode())


def field_payload(f):
    t = f["type"]
    out = {"name": f["name"], "type": t}
    if t in ("singleSelect", "multipleSelects"):
        out["options"] = {"choices": [{"name": o} for o in f.get("options", []) if o != ""]}
    elif t == "number":
        out["options"] = {"precision": f.get("precision", 0)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pat", required=True)
    ap.add_argument("--base-id", required=True)
    ap.add_argument("--schema", default="airtable_schema.json")
    a = ap.parse_args()
    schema = json.load(open(a.schema, encoding="utf-8"))
    creatable = [f for f in schema["fields"] if f["type"] not in COMPUTED]
    payload = {"name": schema.get("table_name", "Pages Master"),
               "fields": [field_payload(f) for f in creatable]}
    res = post(META.format(base=a.base_id), a.pat, payload)
    print("[OK] Created table id=" + res.get("id", "?") + " with " + str(len(creatable)) + " fields.")
    print("[!] Create computed fields in the Airtable UI (API cannot):")
    for cf in schema.get("computed_fields_create_in_ui", []):
        print("    - " + cf["name"] + " (" + cf["type"] + ")")


if __name__ == "__main__":
    main()
