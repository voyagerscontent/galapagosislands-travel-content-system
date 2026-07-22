---
name: pattern-breaker
description: Two-phase, deterministic-first AI-pattern detector and constrained restructurer. Phase 1 uses pure math (no LLM) to flag mechanical writing signatures — repetitive rhythm, low burstiness, formulaic n-grams, uniform sentence/paragraph structure, formulaic transitions. Phase 2 hands ONLY the flagged spans to Claude Sonnet under strict non-deviation rules to break the pattern, injecting Markov-based rhythm variation without changing any fact. Use when the user wants to detect and de-pattern AI-sounding copy for Voyagers / Latin Trails / galapagosislands.travel and related sites, or run it inside n8n. Complements human-dictionary-travel (word/phrase replacement); this one restructures rhythm and form.
version: 1.0.0
---

# pattern-breaker

Deterministic **detection** + tightly-constrained **restructuring** in two phases.
No hallucination path: the model can only vary form, never facts.

## When to use

- Detect whether a piece of copy carries mechanical/AI-pattern signatures.
- Break those patterns (rhythm, burstiness, formulas) while preserving meaning.
- Run detection-only as a fast, free, deterministic gate (no LLM, no key).
- Wire it into n8n via the FastAPI service.

Pair with `human-dictionary-travel` (word/phrase swaps) — run that first to fix
vocabulary, then `pattern-breaker` to fix rhythm and structure.

## The two phases

### Phase 1 — deterministic detector (pure Python, no LLM)
Computes numeric metrics and compares them to **hardcoded thresholds** in
`config/thresholds.json`. Same input + same thresholds => same flags. Factors:

| Factor | Detects | Requirement |
|---|---|---|
| `ngram_formula` | repeated 3/4/5-word templates | "pattern/formula within text", "repetitive formulas" |
| `sentence_rhythm` | low length-CV or high lag-1 autocorrelation | "repetitive rhythm" |
| `burstiness` | low sentence/word length variation | "lack of burstiness" |
| `sentence_structure` | repeated openings / runs of same first word | "pattern in sentences" |
| `paragraph_pattern` | uniform paragraph lengths / parallel openings | "pattern in paragraphs" |
| `transition_formula` | overused connectives (Moreover, Furthermore…) | formulaic transitions |

Output: per-factor flags with the metric, the threshold breached, and the exact
character spans to hand to Phase 2. If nothing breaches, the text is returned
unchanged and Phase 2 never runs.

### Phase 2 — constrained restructurer (Claude Sonnet)
Runs **only if Phase 1 flagged**. For each flagged span, in isolation:

1. Build **Markov cadence seeds** from the span's own words + the
   `human_corpus.json` travel corpus (2,307 real forum sentences pulled from
   `voyagerscontent/human-dictionary-travel`). Seeds are rhythm inspiration, not
   facts.
2. Send the span + the detected pattern reasons + a randomized paragraph shape to
   Claude Sonnet under a **hardcoded non-deviation system prompt**: break the
   pattern, force sentence-length variation (burstiness), vary openings, drop
   formulaic connectives — and add/remove **zero** facts.
3. Run the deterministic **fact-safety guard**: any NEW number or named entity =>
   HARD FAIL => re-prompt (up to `verify_max_passes`). If a fact was dropped =>
   accept but mark **major change**.
4. Anything flagged major, or unfixable after retries, is **highlighted in light
   blue** (`<span class="pb-review" style="background-color:#cfe8ff">…</span>` in
   HTML, `[[PB-REVIEW]]…[[/PB-REVIEW]]` in plain text) so an editor can verify.

The pipeline then **re-runs Phase 1** on the output to confirm flags cleared,
iterating up to `verify_max_passes`.

## Guarantees

- **Deterministic detection.** No randomness in Phase 1.
- **No invented facts.** Claude output that introduces a number/entity is
  rejected automatically before it can ship.
- **Auditable.** Every flag reports its metric and threshold; every rewrite
  reports its guard result and pass count.
- **Editor-in-the-loop.** Major changes are visually flagged light blue.

## Usage

```bash
# Detection only (no key, deterministic):
python3 cli.py detect input.txt

# Full run (needs Claude): set ONE of these:
export ANTHROPIC_API_KEY=sk-ant-...      # direct
export PB_USE_PROXY=1                     # behind the credential proxy
python3 cli.py process input.txt --text-only
```

Service (for n8n / other repos):
```bash
uvicorn service.api:app --host 0.0.0.0 --port 8080
# POST /detect | /restructure | /process   {"text": "..."}
```

## Configuration

All sensitivity lives in `config/thresholds.json`. Editing those numbers is the
only supported way to change behaviour — nothing is left to model judgment.
`PB_CLAUDE_MODEL` selects the Sonnet model (default `claude-sonnet-4-6`).
