#!/usr/bin/env python3
"""
Deploy the native pattern-breaker workflow to n8n cloud.

Source of truth = this repo. This script:
  1. regenerates n8n_workflow_native.json from the .js source files,
  2. PUT-updates the EXISTING workflow in n8n (never creates a duplicate),
  3. re-activates it so the webhook stays live.

Env vars (set as GitHub Action secrets / repo variables):
  N8N_BASE_URL     e.g. https://voyagerscontent.app.n8n.cloud   (required)
  N8N_API_KEY      n8n public API key                            (required)
  N8N_WORKFLOW_ID  target workflow id (default: 2ToiqCivCTCj74oK)

Exit 0 on success, non-zero on any failure (so CI fails loudly).
"""
import json, os, sys, subprocess, urllib.request, urllib.error, pathlib

HERE = pathlib.Path(__file__).resolve().parent
WF_JSON = HERE / "n8n_workflow_native.json"

BASE = os.environ.get("N8N_BASE_URL", "").rstrip("/")
KEY = os.environ.get("N8N_API_KEY", "")
WFID = os.environ.get("N8N_WORKFLOW_ID", "2ToiqCivCTCj74oK")

if not BASE or not KEY:
    print("ERROR: N8N_BASE_URL and N8N_API_KEY must be set.", file=sys.stderr)
    sys.exit(2)


def _api_curl(method, path, body=None):
    """Transport used behind a credential proxy (curl trusts the proxy CA).
    The proxy injects X-N8N-API-KEY, so no key is placed on the command line."""
    import tempfile
    url = f"{BASE}/api/v1{path}"
    cmd = ["curl", "-sS", "-o", "-", "-w", "\n%{http_code}", "-X", method, url,
           "-H", "accept: application/json"]
    tmp = None
    if body is not None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(body, f); tmp = f.name
        cmd += ["-H", "content-type: application/json", "-d", f"@{tmp}"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        text = out.stdout
        nl = text.rfind("\n")
        code = int(text[nl + 1:].strip() or 0)
        raw = text[:nl] if nl >= 0 else text
        return code, (json.loads(raw) if raw.strip() else {})
    finally:
        if tmp:
            try: os.unlink(tmp)
            except OSError: pass


def api(method, path, body=None):
    # Behind the sandbox credential proxy, use curl (urllib can't verify the
    # proxy's self-signed cert). In normal CI there is no proxy -> urllib.
    if os.environ.get("PB_USE_PROXY") == "1":
        return _api_curl(method, path, body)
    url = f"{BASE}/api/v1{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("accept", "application/json")
    req.add_header("X-N8N-API-KEY", KEY)
    if data is not None:
        req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:500]}


def main():
    # 1. regenerate JSON from JS source (single source of truth)
    print("Regenerating workflow JSON from .js source ...")
    subprocess.run([sys.executable, str(HERE / "build_native_workflow.py")], check=True)

    w = json.loads(WF_JSON.read_text(encoding="utf-8"))
    payload = {
        "name": w["name"],
        "nodes": w["nodes"],
        "connections": w["connections"],
        "settings": w.get("settings", {"executionOrder": "v1"}),
    }

    # 2. verify the workflow exists (fail clearly if the id is wrong)
    st, cur = api("GET", f"/workflows/{WFID}")
    if st != 200:
        print(f"ERROR: workflow {WFID} not found (HTTP {st}): {cur}", file=sys.stderr)
        sys.exit(1)
    print(f"Target workflow: {cur.get('name')} (id {WFID})")

    # 3. update
    st, res = api("PUT", f"/workflows/{WFID}", payload)
    if st != 200:
        print(f"ERROR: update failed (HTTP {st}): {res}", file=sys.stderr)
        sys.exit(1)
    print("Updated workflow definition.")

    # 4. re-activate (PUT can leave it inactive on some n8n versions)
    st, res = api("POST", f"/workflows/{WFID}/activate")
    if st != 200:
        print(f"WARNING: activate returned HTTP {st}: {res}", file=sys.stderr)
    else:
        print(f"Active: {res.get('active')}")

    print("Deploy complete. Webhook:",
          f"{BASE}/webhook/pattern-breaker")


if __name__ == "__main__":
    main()
