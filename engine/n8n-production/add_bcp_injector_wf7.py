#!/usr/bin/env python3
"""Wire the BCP lexical injector at the ABSOLUTE END — after the auditor passes.

The injector used to run at the end of WFP5 (humanize), but WFP6 Polishing runs
after it and REWRITES the prose, wiping the injected salt/words. So it now runs in
WFP7, on the PASS path, AFTER the QA gate + LLM auditor have validated the polished
page — the last thing before Editor Review, exactly as the spec requires
("runs at the absolute end so subsequent passes do not overwrite the injected words").

  Output OK? --pass--> BCP Inject (HTML) --> Advance to Editor Review
                                              (writes the injected Polished Content)

It operates on the polished HTML, per <p> only (never <title>/<meta>/JSON-LD): swaps
generic adjectives for contextual high-BCP words and splices verbatim human salt into
paragraph middles — up to 2 LONG sentences + 3 short PHRASES per article. Pure code.
"""
import json, os, re, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP7_auditor.json")
LEXICON = os.path.join(HERE, "..", "..", "content-pipeline", "data", "lexicon.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "na9GWyR851UHSlbP"

KEYWORDS_PER_CAT, ADJ_PER_CAT = 25, 45
CLEAN = re.compile(r"^[a-z]{4,}$")
TAG_KEYWORDS = [["snorkel", "snorkel"], ["dive", "snorkel"], ["panga", "cruise"],
                ["cruise", "cruise"], ["wildlife", "wildlife"], ["bird", "wildlife"],
                ["sea lion", "wildlife"], ["island", "destination"], ["highland", "destination"]]


def compile_compact(lex):
    cats, fallback = [], []
    for group, catmap in lex.get("pools", {}).items():
        for cat, b in catmap.items():
            adjs = [w for w in (b.get("adjective", []) + b.get("sensory", [])) if CLEAN.match(w)][:ADJ_PER_CAT]
            kws = [w for w in (b.get("noun", []) + b.get("place", [])) if CLEAN.match(w) and len(w) >= 5][:KEYWORDS_PER_CAT]
            if adjs:
                cats.append({"name": cat, "keywords": kws, "adjectives": adjs})
                if group == "feeling":
                    fallback += adjs
    return {
        "generic_adjectives": lex.get("generic_adjectives", []),
        "categories": cats,
        "fallback_adjectives": sorted(set(fallback))[:120] or ["vivid"],
        "human_sentences": [{"text": s["text"], "kind": s.get("kind", "phrase"),
                             "tags": s.get("tags", ["general"])} for s in lex.get("human_sentences", [])],
        "tag_keywords": TAG_KEYWORDS,
    }


JS = r"""
const DATA = __DATA__;
const rec = ($items('Re-check and Claim (guarded)')[0] || {json:{}}).json;
const meta = $json || {};
let html = String(rec['Polished Content'] || '');
const priorLog = String(rec['De-AI Log'] || '');
function seed(s){let h=2166136261>>>0;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)>>>0;}return h>>>0;}
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const genRe = new RegExp('\\b(' + DATA.generic_adjectives.map(esc).join('|') + ')\\b','gi');
const CAP = { long: 2, phrase: 3 };
const used = new Set();
let swaps = 0, longN = 0, phraseN = 0;
html = html.replace(/<p\b([^>]*)>([\s\S]*?)<\/p>/gi, function(m, attrs, inner){
  const low = inner.replace(/<[^>]+>/g,' ').toLowerCase();
  let best = null, bh = 0;
  for(const c of DATA.categories){ let h=0; for(const k of c.keywords){ if(low.indexOf(k)>=0) h++; } if(h>bh){bh=h;best=c;} }
  const pool = (best && best.adjectives.length) ? best.adjectives : DATA.fallback_adjectives;
  let p = inner.replace(genRe, function(w, g, off){
    if(!pool.length) return w;
    const rep = pool[seed(w + off + (best?best.name:'')) % pool.length];
    if(!rep || rep.toLowerCase() === w.toLowerCase()) return w;
    swaps++;
    return (w[0] === w[0].toUpperCase()) ? rep[0].toUpperCase()+rep.slice(1) : rep;
  });
  const sents = p.replace(/<[^>]+>/g,' ').split(/(?<=[.!?])\s+/).filter(function(s){return s.trim();});
  if(sents.length >= 3 && (longN < CAP.long || phraseN < CAP.phrase)){
    const ptags = new Set(['general']);
    for(const pair of DATA.tag_keywords){ if(low.indexOf(pair[0])>=0) ptags.add(pair[1]); }
    const cands = DATA.human_sentences.map(function(s,i){return [i,s];}).filter(function(x){
      const k = x[1].kind === 'long' ? 'long' : 'phrase';
      const budget = k === 'long' ? (longN < CAP.long) : (phraseN < CAP.phrase);
      return !used.has(x[0]) && budget && x[1].tags.some(function(t){return ptags.has(t);});
    });
    cands.sort(function(a,b){
      const ao=a[1].tags.filter(function(t){return ptags.has(t);}).length;
      const bo=b[1].tags.filter(function(t){return ptags.has(t);}).length;
      if(bo!==ao) return bo-ao; return seed(inner+a[0]) - seed(inner+b[0]);
    });
    if(cands.length){
      const chosen = cands[0][1]; used.add(cands[0][0]);
      if(chosen.kind === 'long') longN++; else phraseN++;
      const positions = []; let mm; const re = /[.!?]\s+/g;
      while((mm = re.exec(p)) !== null) positions.push(mm.index + mm[0].length);
      if(positions.length){
        const target = p.length / 2;
        let bestPos = positions[0];
        for(const pos of positions){ if(Math.abs(pos-target) < Math.abs(bestPos-target)) bestPos = pos; }
        p = p.slice(0, bestPos) + chosen.text.trim() + ' ' + p.slice(bestPos);
      } else {
        p = p + ' ' + chosen.text.trim();
      }
    }
  }
  return '<p' + attrs + '>' + p + '</p>';
});
const bcpLog = 'BCP injector @publish (no LLM): ' + swaps + ' adj swap(s), ' + longN + ' long + ' + phraseN + ' phrase salt';
return [{ json: {
  recordId: meta.recordId || rec.id || '', baseId: meta.baseId || '', tableId: meta.tableId || '',
  notes: meta.notes || '', artifact: html,
  deaiLog: (priorLog ? priorLog + '\n' : '') + bcpLog
} }];
"""


def main():
    lex = json.load(open(LEXICON, encoding="utf-8"))
    js = JS.replace("__DATA__", json.dumps(compile_compact(lex), ensure_ascii=False))

    wf = json.load(open(WF, encoding="utf-8"))
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "BCP Inject (HTML)"]
    nodes = {n["name"]: n for n in wf["nodes"]}
    ax, ay = nodes["Advance to Editor Review"]["position"]
    nodes["Advance to Editor Review"]["position"] = [ax + 200, ay]

    node = {"parameters": {"jsCode": js}, "id": "wf7-bcp-inject",
            "name": "BCP Inject (HTML)", "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": [ax, ay]}
    wf["nodes"].append(node)

    c = wf["connections"]
    # Output OK? pass branch -> BCP Inject (HTML) -> Advance to Editor Review
    c["Output OK?"] = {"main": [
        [{"node": "BCP Inject (HTML)", "type": "main", "index": 0}],
        [{"node": "Route to Needs Attention", "type": "main", "index": 0}],
    ]}
    c["BCP Inject (HTML)"] = {"main": [[{"node": "Advance to Editor Review", "type": "main", "index": 0}]]}

    # Advance now also writes the injected Polished Content + updated De-AI Log
    adv = nodes["Advance to Editor Review"]["parameters"]["columns"]["value"]
    adv["Polished Content"] = "={{ $json.artifact }}"
    adv["De-AI Log"] = "={{ $json.deaiLog }}"

    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"WFP7: BCP Inject (HTML) added post-audit ({os.path.getsize(WF)//1024} KB).")

    pub = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not pub:
        print("no key — local only."); return
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"],
            "settings": wf.get("settings", {"executionOrder": "v1"})}
    req = urllib.request.Request(N8N + "/api/v1/workflows/" + WID, data=json.dumps(body).encode(),
                                 headers={"X-N8N-API-KEY": pub, "Content-Type": "application/json"}, method="PUT")
    try:
        d = json.load(urllib.request.urlopen(req))
        print("pushed to n8n:", "ok" if d.get("id") else "??", "| active:", d.get("active"))
    except urllib.error.HTTPError as e:
        print("push ERR %d %s" % (e.code, e.read().decode()[:300]))


if __name__ == "__main__":
    main()
