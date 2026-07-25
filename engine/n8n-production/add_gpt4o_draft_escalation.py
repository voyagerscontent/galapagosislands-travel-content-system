#!/usr/bin/env python3
"""WFP3: escalate the re-draft to GPT-4o once burstiness has failed twice.

Escalation ladder (see [[burstiness-retry-escalation]]):
  retries 0-1 -> re-draft on Claude + CV feedback in the prompt
  retries >=2 -> re-draft on GPT-4o (a different model's paragraph rhythm can break a
                 run of flat Claude drafts) + the same CV feedback
  after 3     -> advisory (WFP5 gate)

IMPORTANT — why the IF is DOWNSTREAM of Claude, not upstream:
  The draft LLM is the langchain `@n8n/n8n-nodes-langchain.anthropic` node. Feeding it
  from a multi-output node (an IF's branch) makes the Anthropic request 400 ("Bad
  request - please check your parameters") even though the item data is byte-identical
  to a direct feed — an n8n langchain quirk. So Claude MUST stay wired directly from
  "Re-check and Claim". We branch on the model AFTER Claude runs:

  Re-check ─▶ Run Stage Agent (Claude, DIRECT) ─▶ Draft on GPT-4o? (IF retries>=2)
      false (0-1) ─▶ Validate Output              (use Claude's draft)
      true  (>=2) ─▶ Compose Draft Prompt (Set) ─▶ Run Stage Agent (GPT-4o) ─▶ Validate Output

  Trade-off: at retry>=2 Claude still runs and its draft is discarded (one wasted Opus
  call, but only on retries 2-3, which are rare). The alternative — branching before
  Claude — is the exact topology that 400s, so we accept the waste.

  The Compose node sits after Claude, so $json there is Claude's OUTPUT, not the record.
  Its prompt therefore reads record fields via $('Re-check and Claim (guarded)').item.json
  (the applier rewrites $json[ -> that reference when copying Claude's prompt).

Run:  N8N_API_KEY=... python engine/n8n-production/add_gpt4o_draft_escalation.py
"""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP3_draft.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "eExgOTVFIoCuJb0D"
OPENAI_CRED = {"id": "OFoTjKuoF9PqAZDU", "name": "OpenAI GPT-4o (burstiness escalation)"}
NEW = ("Draft on GPT-4o?", "Compose Draft Prompt", "Run Stage Agent (GPT-4o)")
RECHECK = "Re-check and Claim (guarded)"

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
    # Claude keeps $json (it is fed directly from Re-check). The GPT-4o copy sits after
    # Claude, so rewrite $json[ -> $('Re-check...').item.json[ for record-field reads.
    claude_prompt = claude["parameters"]["messages"]["values"][0]["content"]
    gpt_prompt = claude_prompt.replace("$json[", "$('%s').item.json[" % RECHECK)
    rx, ry = bn[RECHECK]["position"]
    cx, cy = claude["position"]

    def node(name, ntype, params, pos, nid, tv, creds=None):
        n = {"parameters": params, "id": nid, "name": name, "type": ntype, "typeVersion": tv, "position": pos}
        if creds:
            n["credentials"] = creds
        return n

    router = node("Draft on GPT-4o?", "n8n-nodes-base.if", {"conditions": {"number": [
        {"value1": "={{ ($('%s').item.json['Burstiness Retries'] || 0) }}" % RECHECK,
         "operation": "largerEqual", "value2": 2}]}},
        [cx + 220, cy], "wfp3-gpt4o-router", 1)
    compose = node("Compose Draft Prompt", "n8n-nodes-base.set", {
        "assignments": {"assignments": [
            {"id": "prompt-field", "name": "prompt", "type": "string", "value": gpt_prompt}]},
        "includeOtherFields": True, "options": {}},
        [cx + 420, cy - 160], "wfp3-gpt4o-compose", 3.4)
    gpt = node("Run Stage Agent (GPT-4o)", "n8n-nodes-base.httpRequest", {
        "method": "POST", "url": "https://api.openai.com/v1/chat/completions",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "openAiApi",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": ("={{ ({ model: \"gpt-4o\", temperature: 1, max_tokens: 16000, "
                     "messages: [ { role: \"user\", content: $json.prompt } ] }) }}"),
        "options": {"timeout": 300000}},
        [cx + 620, cy - 160], "wfp3-gpt4o-http", 4.2, creds={"openAiApi": OPENAI_CRED})

    wf["nodes"] += [router, compose, gpt]

    vo = bn["Validate Output"]["parameters"]
    if VO_OLD in vo["jsCode"]:
        vo["jsCode"] = vo["jsCode"].replace(VO_OLD, VO_NEW)
    elif "$json.choices" not in vo["jsCode"]:
        raise SystemExit("Validate Output raw-extractor changed — update VO_OLD before re-running.")

    c = wf["connections"]
    c[RECHECK] = {"main": [[{"node": "Run Stage Agent", "type": "main", "index": 0}]]}         # DIRECT
    c["Run Stage Agent"] = {"main": [[{"node": "Draft on GPT-4o?", "type": "main", "index": 0}]]}
    c["Draft on GPT-4o?"] = {"main": [
        [{"node": "Compose Draft Prompt", "type": "main", "index": 0}],   # true  (>=2) -> GPT-4o
        [{"node": "Validate Output", "type": "main", "index": 0}],        # false (0-1) -> Claude draft
    ]}
    c["Compose Draft Prompt"] = {"main": [[{"node": "Run Stage Agent (GPT-4o)", "type": "main", "index": 0}]]}
    c["Run Stage Agent (GPT-4o)"] = {"main": [[{"node": "Validate Output", "type": "main", "index": 0}]]}

    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"WFP3: GPT-4o escalation (downstream IF, retries>=2). {os.path.getsize(WF)//1024} KB")

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
