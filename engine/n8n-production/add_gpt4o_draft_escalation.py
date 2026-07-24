#!/usr/bin/env python3
"""WFP3: escalate the re-draft to GPT-4o once burstiness has failed twice.

Escalation ladder (see [[burstiness-retry-escalation]]):
  retries 0-1 -> re-draft on Claude (unchanged) + CV feedback in the prompt
  retries >=2 -> re-draft on GPT-4o (a different model's paragraph rhythm can break
                 a run of flat Claude drafts) + the same CV feedback
  after 3     -> advisory (WFP5 gate)

Design goal: the working Claude path stays BYTE-FOR-BYTE unchanged. We only insert an
IF router between "Re-check and Claim" and the agents; its FALSE branch feeds the
existing Claude node directly (same item, unchanged). The GPT-4o branch gets a Set node
that pre-resolves the SAME prompt expression to a plain string ($json.prompt) so the
HTTP node can embed it in a JSON body without nesting {{ }} expressions.

  Re-check and Claim ─▶ Draft on GPT-4o? (IF: Burstiness Retries >= 2)
      false ─▶ Run Stage Agent (Claude)                    [UNCHANGED]
      true  ─▶ Compose Draft Prompt (Set) ─▶ Run Stage Agent (GPT-4o, HTTP)
      both  ─▶ Validate Output  (extended to read choices[0].message.content)

The GPT-4o prompt is copied from the Claude node at apply-time — single source of truth
is the Claude node; re-run this applier after editing the draft prompt to resync.

Run:  N8N_API_KEY=... python engine/n8n-production/add_gpt4o_draft_escalation.py
"""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP3_draft.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "eExgOTVFIoCuJb0D"
OPENAI_CRED = {"id": "OFoTjKuoF9PqAZDU", "name": "OpenAI GPT-4o (burstiness escalation)"}
NEW = ("Draft on GPT-4o?", "Compose Draft Prompt", "Run Stage Agent (GPT-4o)")

# Validate Output already handles the Anthropic (content[]) and classic (message.content)
# shapes. Add the raw Chat Completions shape (choices[0].message.content) up front.
VO_OLD = ("let raw = Array.isArray($json.content) ? $json.content.filter(b=>b.type==='text')"
          ".map(b=>b.text).join('') : ($json.message && $json.message.content ? "
          "$json.message.content : ($json.text||''));")
VO_NEW = ("let raw = Array.isArray($json.content) ? $json.content.filter(b=>b.type==='text')"
          ".map(b=>b.text).join('') : (($json.choices && $json.choices[0] && "
          "$json.choices[0].message && $json.choices[0].message.content) ? "
          "$json.choices[0].message.content : ($json.message && $json.message.content ? "
          "$json.message.content : ($json.text||'')));")


def main():
    wf = json.load(open(WF, encoding="utf-8"))
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] not in NEW]
    for nm in NEW:
        wf["connections"].pop(nm, None)
    bn = {n["name"]: n for n in wf["nodes"]}

    claude = bn["Run Stage Agent"]
    prompt_expr = claude["parameters"]["messages"]["values"][0]["content"]  # the '=' expression
    rx, ry = bn["Re-check and Claim (guarded)"]["position"]

    def node(name, ntype, params, pos, nid, tv, creds=None):
        n = {"parameters": params, "id": nid, "name": name, "type": ntype, "typeVersion": tv, "position": pos}
        if creds:
            n["credentials"] = creds
        return n

    router = node("Draft on GPT-4o?", "n8n-nodes-base.if", {"conditions": {"number": [
        {"value1": "={{ $json['Burstiness Retries'] || 0 }}", "operation": "largerEqual", "value2": 2}]}},
        [rx + 200, ry], "wfp3-gpt4o-router", 1)
    compose = node("Compose Draft Prompt", "n8n-nodes-base.set", {
        "assignments": {"assignments": [
            {"id": "prompt-field", "name": "prompt", "type": "string", "value": prompt_expr}]},
        "includeOtherFields": True, "options": {}},
        [rx + 400, ry - 140], "wfp3-gpt4o-compose", 3.4)
    gpt = node("Run Stage Agent (GPT-4o)", "n8n-nodes-base.httpRequest", {
        "method": "POST", "url": "https://api.openai.com/v1/chat/completions",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "openAiApi",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": ("={{ ({ model: \"gpt-4o\", temperature: 1, max_tokens: 16000, "
                     "messages: [ { role: \"user\", content: $json.prompt } ] }) }}"),
        "options": {"timeout": 300000}},
        [rx + 620, ry - 140], "wfp3-gpt4o-http", 4.2, creds={"openAiApi": OPENAI_CRED})

    wf["nodes"] += [router, compose, gpt]

    # extend Validate Output
    vo = bn["Validate Output"]["parameters"]
    if VO_OLD in vo["jsCode"]:
        vo["jsCode"] = vo["jsCode"].replace(VO_OLD, VO_NEW)
    elif "$json.choices" not in vo["jsCode"]:
        raise SystemExit("Validate Output raw-extractor line changed — update VO_OLD before re-running.")

    c = wf["connections"]
    c["Re-check and Claim (guarded)"] = {"main": [[{"node": "Draft on GPT-4o?", "type": "main", "index": 0}]]}
    c["Draft on GPT-4o?"] = {"main": [
        [{"node": "Compose Draft Prompt", "type": "main", "index": 0}],   # true  -> GPT-4o branch
        [{"node": "Run Stage Agent", "type": "main", "index": 0}],        # false -> Claude (unchanged)
    ]}
    c["Compose Draft Prompt"] = {"main": [[{"node": "Run Stage Agent (GPT-4o)", "type": "main", "index": 0}]]}
    c["Run Stage Agent (GPT-4o)"] = {"main": [[{"node": "Validate Output", "type": "main", "index": 0}]]}
    # Run Stage Agent (Claude) -> Validate Output already exists, unchanged.

    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"WFP3: GPT-4o escalation branch added (retries>=2). {os.path.getsize(WF)//1024} KB")

    key = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not key:
        print("no key — local only."); return
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})}
    req = urllib.request.Request(N8N + "/api/v1/workflows/" + WID, data=json.dumps(body).encode(),
                                 headers={"X-N8N-API-KEY": key, "Content-Type": "application/json"}, method="PUT")
    try:
        d = json.load(urllib.request.urlopen(req))
        print("pushed to n8n:", "ok" if d.get("id") else "??", "| active:", d.get("active"))
    except urllib.error.HTTPError as e:
        print("push ERR %d %s" % (e.code, e.read().decode()[:300]))


if __name__ == "__main__":
    main()
