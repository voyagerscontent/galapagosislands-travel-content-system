#!/usr/bin/env python3
"""Monthly self-update for the AI-signal blocklist — PROPOSE a diff, never auto-apply.

Fetches the live sources, finds NEW candidate tells not already tracked, measures
each against Juan's human corpus (so it can never promote a term he actually uses),
auto-tiers them, and writes:
  - ai_signal_blocklist.proposed.json   (the would-be new blocklist)
  - ai_signal_update_report.md          (a human-readable diff to review)

It does NOT touch ai_signal_blocklist.json. A human (or a scheduled agent that
opens a PR) reviews the report and, if good, promotes the proposed file. This is
the "propose diff for approval" contract — production is never changed unattended.

Run monthly (cron / scheduled agent):  python engine/n8n-production/update_ai_signals.py
"""
import json, os, re, urllib.request, datetime

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BLOCKLIST = os.path.join(HERE, "ai_signal_blocklist.json")
CORPUS_DIR = os.path.join(ROOT, "context-pack", "brand-voice", "juan-magallanes-source")
HARD_MAX = 0.02

WIKI_API = ("https://en.wikipedia.org/w/api.php?action=parse"
            "&page=Wikipedia:Signs_of_AI_writing&prop=wikitext&format=json")
ARXIV = ["https://arxiv.org/abs/2301.11305", "https://arxiv.org/abs/2503.01659"]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "galapagos-content-bot/1.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def corpus_per1k():
    text = ""
    for f in os.listdir(CORPUS_DIR):
        text += "\n" + open(os.path.join(CORPUS_DIR, f), encoding="utf-8", errors="replace").read()
    low = text.lower()
    wc = len(text.split())
    def per1k(term):
        n = len(re.findall(r"\b" + re.escape(term.lower()) + r"\b", low))
        return (n / wc) * 1000 if wc else 0
    return per1k, wc


def extract_candidates(wikitext):
    """Pull only the RELIABLE example-phrase signal: {{tq|...}} (Wikipedia's
    'text quote' template, used to quote actual AI-writing examples) and short
    ''italic'' emphases. Deliberately conservative — the bulleted-list heuristic
    pulls editorial instructions ('add spouse if reliably sourced'), so it's out.
    The corpus filter + human review are still the final safety net."""
    cands = set()
    for m in re.findall(r"\{\{tq\|([^}|]{2,40})\}\}", wikitext, re.I):
        cands.add(m.strip().lower())
    for m in re.findall(r"''([a-z][a-z \-]{2,30})''", wikitext, re.I):
        cands.add(m.strip().lower())
    # lexical hygiene: 1-3 words, letters only, no wiki/editorial noise
    bad = {"the", "and", "for", "with", "that", "this", "cite", "ref", "see also",
           "references", "about me", "access-date", "ai vocabulary", "ai-generated"}
    out = set()
    for c in cands:
        c = re.sub(r"\s+", " ", c).strip()
        if c in bad or c.startswith("http"):
            continue
        if not re.fullmatch(r"[a-z][a-z \-]+[a-z]", c):
            continue
        if len(c.split()) > 3:
            continue
        out.add(c)
    return out


def main():
    bl = json.load(open(BLOCKLIST, encoding="utf-8"))
    known = set(w.lower() for w in
                bl["tier_a_words"] + bl["tier_b_words"] + bl["tier_a_phrases"] + bl["tier_b_phrases"])

    notes = []
    try:
        wikitext = json.loads(fetch(WIKI_API))["parse"]["wikitext"]["*"]
        cands = extract_candidates(wikitext)
        notes.append(f"Wikipedia:Signs_of_AI_writing fetched ({len(wikitext)} chars, {len(cands)} raw candidates).")
    except Exception as e:
        cands = set()
        notes.append(f"WIKIPEDIA FETCH FAILED: {e}. No candidates this run — re-run where outbound HTTP is allowed.")
    for u in ARXIV:
        try:
            fetch(u); notes.append(f"reachable: {u}")
        except Exception as e:
            notes.append(f"unreachable: {u} ({e})")

    per1k, wc = corpus_per1k()
    new = sorted(c for c in cands if c not in known)
    # Candidates come from the AI-writing catalog, so they ARE AI traces → all
    # propose as HARD (TIER-A) regardless of whether Juan uses them (user's rule).
    # Corpus density is shown only to flag which bans would touch his voice.
    add_a = [(c, round(per1k(c), 3)) for c in new]
    add_b = []
    overlap = [(c, round(per1k(c), 3)) for c in new if per1k(c) > HARD_MAX]

    proposed = json.loads(json.dumps(bl))
    for c, _ in add_a:
        (proposed["tier_a_phrases"] if " " in c else proposed["tier_a_words"]).append(c)
    for k in ("tier_a_words", "tier_a_phrases", "tier_b_words", "tier_b_phrases"):
        proposed[k] = sorted(set(proposed[k]))
    proposed["_proposed_on"] = datetime.date.today().isoformat()

    json.dump(proposed, open(os.path.join(HERE, "ai_signal_blocklist.proposed.json"), "w"),
              indent=2, ensure_ascii=False)

    rep = [f"# AI-signal blocklist — proposed update ({datetime.date.today().isoformat()})", ""]
    rep += ["## Sources", *[f"- {n}" for n in notes], ""]
    rep.append(f"Human corpus: {wc} words. New candidates: {len(new)} "
               f"— all proposed as hard TIER-A (they are AI traces; banned even if Juan uses them).\n")
    rep.append("## Proposed TIER-A additions (hard-fail)")
    rep += [f"- `{c}`  ({d}/1k in corpus)" for c, d in add_a] or ["- (none)"]
    rep.append("\n## Of those, terms Juan actually uses (banned anyway, per rule — expect reconstruction work)")
    rep += [f"- `{c}`  ({d}/1k)" for c, d in overlap] or ["- (none)"]
    rep += ["", "## To apply", "Review the list above. If good, replace ai_signal_blocklist.json with",
            "ai_signal_blocklist.proposed.json (or cherry-pick terms) and commit. Nothing was",
            "changed automatically."]
    open(os.path.join(HERE, "ai_signal_update_report.md"), "w").write("\n".join(rep))

    print(f"proposed {len(add_a)} TIER-A + {len(add_b)} TIER-B additions. "
          f"See ai_signal_update_report.md (nothing applied).")


if __name__ == "__main__":
    main()
