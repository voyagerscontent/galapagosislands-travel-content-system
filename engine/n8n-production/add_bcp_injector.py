#!/usr/bin/env python3
"""Wire a deterministic BCP lexical injector into the LIVE WFP5, at the absolute end.

Compiles a COMPACT version of content-pipeline/data/lexicon.json (built from the
High-Entropy Injectors workbook) into a JS code node and inserts it after the
De-AI Dictionary node:

  ... -> De-AI Dictionary (no-LLM) -> BCP Inject (no-LLM) -> Output OK? -> ...

The node runs LAST so nothing overwrites the injected low-probability words. It is
pure code (no LLM, no POS): per paragraph it detects the context category from
distinctive keyword hits, swaps generic high-probability adjectives for a clean
high-BCP adjective from that category's pool, and splices a verbatim human "salt"
sentence into a paragraph's middle. Paragraph count is preserved. The swap/salt
counts are appended to the record's "De-AI Log".

Verb replacement is intentionally NOT ported live (breaks transitivity without POS).
Re-run after rebuilding the lexicon.
"""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(__file__)
WF = os.path.join(HERE, "WFP5_humanize.json")
LEXICON = os.path.join(HERE, "..", "..", "content-pipeline", "data", "lexicon.json")
N8N = "https://voyagerscontent.app.n8n.cloud"
WID = "yh9kMFkbPY34vmVJ"

KEYWORDS_PER_CAT = 25
ADJ_PER_CAT = 45
CLEAN = __import__("re").compile(r"^[a-z]{4,}$")

TAG_KEYWORDS = [["snorkel", "snorkel"], ["dive", "snorkel"], ["panga", "cruise"],
                ["cruise", "cruise"], ["wildlife", "wildlife"], ["bird", "wildlife"],
                ["sea lion", "wildlife"], ["pack", "packing"], ["bring", "packing"]]


def compile_compact(lex: dict) -> dict:
    cats = []
    fallback = []
    for group, catmap in lex.get("pools", {}).items():
        for cat, buckets in catmap.items():
            adjs = [w for w in (buckets.get("adjective", []) + buckets.get("sensory", []))
                    if CLEAN.match(w)][:ADJ_PER_CAT]
            kws = [w for w in (buckets.get("noun", []) + buckets.get("place", []))
                   if CLEAN.match(w) and len(w) >= 5][:KEYWORDS_PER_CAT]
            if adjs:
                cats.append({"name": cat, "keywords": kws, "adjectives": adjs})
                if group == "feeling":
                    fallback += adjs
    return {
        "generic_adjectives": lex.get("generic_adjectives", []),
        "categories": cats,
        "fallback_adjectives": sorted(set(fallback))[:120] or ["vivid"],
        "human_sentences": lex.get("human_sentences", []),
        "tag_keywords": TAG_KEYWORDS,
    }


JS_TEMPLATE = r"""
const DATA = __DATA__;
const it = $json || {};
let art = String(it.artifact || '');
function seed(s){let h=2166136261>>>0;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)>>>0;}return h>>>0;}
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const genRe = new RegExp('\\b(' + DATA.generic_adjectives.map(esc).join('|') + ')\\b','gi');
const used = new Set();
let swaps = 0, salted = 0;
const paras = art.split(/\n{2,}/);
// Salt sparingly: a few unpredictable human lines per article, not one per
// paragraph. ~1 per 6 eligible paragraphs, capped 2..4.
const eligible = paras.filter(function(p){ return p.split(/(?<=[.!?])\s+/).filter(function(s){return s.trim();}).length >= 3; }).length;
const MAX_SALT = Math.max(2, Math.min(4, Math.floor(eligible / 6)));
const out = paras.map(function(para){
  if(!para.trim()) return para;
  const low = para.toLowerCase();
  let best = null, bh = 0;
  for(const c of DATA.categories){ let h=0; for(const k of c.keywords){ if(low.indexOf(k)>=0) h++; } if(h>bh){bh=h;best=c;} }
  const pool = (best && best.adjectives.length) ? best.adjectives : DATA.fallback_adjectives;
  let p = para.replace(genRe, function(m, g, off){
    if(!pool.length) return m;
    const rep = pool[seed(m + off + (best?best.name:'')) % pool.length];
    if(!rep || rep.toLowerCase() === m.toLowerCase()) return m;
    swaps++;
    return (m[0] === m[0].toUpperCase()) ? rep[0].toUpperCase()+rep.slice(1) : rep;
  });
  const sents = p.split(/(?<=[.!?])\s+/).filter(function(s){return s.trim();});
  if(sents.length >= 3 && DATA.human_sentences.length && salted < MAX_SALT){
    const ptags = new Set(['general']);
    for(const pair of DATA.tag_keywords){ if(low.indexOf(pair[0])>=0) ptags.add(pair[1]); }
    const cands = DATA.human_sentences.map(function(s,i){return [i,s];}).filter(function(x){return !used.has(x[0]);});
    cands.sort(function(a,b){
      const ao=a[1].tags.filter(function(t){return ptags.has(t);}).length;
      const bo=b[1].tags.filter(function(t){return ptags.has(t);}).length;
      if(bo!==ao) return bo-ao;
      return seed(para+a[0]) - seed(para+b[0]);
    });
    if(cands.length && cands[0][1].tags.some(function(t){return ptags.has(t);})){
      const idx=cands[0][0], chosen=cands[0][1]; used.add(idx);
      const mid=Math.floor(sents.length/2);
      p = sents.slice(0,mid).concat([chosen.text]).concat(sents.slice(mid)).join(' ');
      salted++;
    }
  }
  return p;
});
const finalArt = out.join('\n\n');
const bcpLog = 'BCP injector (no LLM): ' + swaps + ' high-entropy adj swap(s), ' + salted + ' salt sentence(s)';
return [{ json: Object.assign({}, it, {
  artifact: finalArt,
  deaiLog: (it.deaiLog ? it.deaiLog + '\n' : '') + bcpLog
}) }];
"""


def main():
    lex = json.load(open(LEXICON, encoding="utf-8"))
    data = compile_compact(lex)
    js = JS_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))

    wf = json.load(open(WF, encoding="utf-8"))
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] != "BCP Inject (no-LLM)"]
    wf["connections"].pop("BCP Inject (no-LLM)", None)
    nodes = {n["name"]: n for n in wf["nodes"]}

    node = {"parameters": {"jsCode": js}, "id": "post-bcp-inject",
            "name": "BCP Inject (no-LLM)", "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": [2900, 300]}
    for nm in ("Output OK?", "Export to Drive", "Advance to Polishing", "Route to Needs Attention"):
        if nm in nodes:
            nodes[nm]["position"] = [max(nodes[nm]["position"][0], 3080), nodes[nm]["position"][1]]
    wf["nodes"].append(node)

    c = wf["connections"]
    # Dictionary -> BCP Inject -> Output OK?
    c["De-AI Dictionary (no-LLM)"] = {"main": [[{"node": "BCP Inject (no-LLM)", "type": "main", "index": 0}]]}
    c["BCP Inject (no-LLM)"] = {"main": [[{"node": "Output OK?", "type": "main", "index": 0}]]}

    # artifact + De-AI Log now come from the BCP node
    for nm in ("Export to Drive", "Advance to Polishing"):
        s = json.dumps(nodes[nm]["parameters"]).replace("$('De-AI Dictionary (no-LLM)')", "$('BCP Inject (no-LLM)')")
        nodes[nm]["parameters"] = json.loads(s)

    json.dump(wf, open(WF, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"WFP5: BCP Inject added at end ({len(data['categories'])} categories, "
          f"{sum(len(c['adjectives']) for c in data['categories'])} adj, "
          f"{os.path.getsize(WF)//1024} KB).")

    pub = os.environ.get("N8N_PUB") or os.environ.get("N8N_API_KEY")
    if not pub:
        print("no N8N key — local only."); return
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
