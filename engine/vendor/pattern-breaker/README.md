# pattern-breaker

**Two-phase, deterministic-first AI-pattern detector + constrained restructurer.**
Phase 1 is pure math (no LLM). Phase 2 uses Claude Sonnet but can only vary
*form*, never *facts*. Same input → same flags, always.

Built for the Voyagers / Latin Trails / galapagosislands.travel content pipeline.
Sibling to [`human-dictionary-travel`](https://github.com/voyagerscontent/human-dictionary-travel):
that repo fixes vocabulary (word/phrase swaps), this one fixes **rhythm and
structure**.

> Design principle (shared with human-dictionary-travel): put the source of
> truth in plain JSON, keep the runtime dumb, and never let a model invent
> content. The only model call is a leashed reword of text a deterministic
> algorithm already flagged.

## What it does

```
                 ┌─────────────────────────── Phase 1 (deterministic, no LLM) ───────────────────────────┐
   raw text ───► │ compute metrics ─► compare to config/thresholds.json ─► flag mechanical spans          │
                 └───────────────────────────��───────────────────────────────────┬──────────────────────┘
                                                                                   │ flagged spans only
                 ┌─────────────────────────── Phase 2 (Claude Sonnet, guarded) ────▼──────────────────────┐
                 │ Markov cadence seeds (own text + human corpus) ─► non-deviation rewrite ─► fact guard   │
                 │ ─► reject new facts / re-prompt ─► light-blue highlight major changes ─► stitch back    │
                 └───────────────────────────────────────────────────────────────┬──────────────────────┘
                                                                                   │
                 ┌─────────────────────────── re-verify (deterministic) ───────────▼──────────────────────┐
                 │ re-run Phase 1 on output; iterate until flags clear or budget spent                     │
                 └────────────────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1 factors (each maps to a requirement)

| Factor | Detects |
|---|---|
| `ngram_formula` | repeated 3/4/5-word templates ("pattern/formula", "repetitive formulas") |
| `sentence_rhythm` | low length coefficient-of-variation / high lag-1 autocorrelation ("repetitive rhythm") |
| `burstiness` | low sentence & word length variation ("lack of burstiness") |
| `sentence_structure` | repeated sentence openings / runs of same first word ("pattern in sentences") |
| `paragraph_pattern` | uniform paragraph lengths / parallel openings ("pattern in paragraphs") |
| `transition_formula` | overused formulaic connectives (Moreover, Furthermore, In conclusion…) |

### Phase 2 guarantees
- **No new facts.** A deterministic guard rejects any Claude output that
  introduces a number or named entity; it re-prompts, then flags for a human.
- **Meaning preserved.** Dropped facts → span accepted but marked *major change*
  and highlighted **light blue** for editor review.
- **Rhythm broken on purpose.** The prompt forces short+long sentence mixing and
  varied openings; Markov seeds (from the text itself + a real travel corpus)
  supply on-topic cadence without inventing content.

## Layout

```
pattern-breaker/
├── config/thresholds.json     # ALL sensitivity lives here (hardcoded, editable)
├── detector/detector.py       # Phase 1 — pure-Python deterministic detector
├── restructurer/
│   ├── markov.py              # seeded Markov cadence-seed generator
│   ├── factguard.py          # deterministic no-new-facts guard
│   └── restructure.py        # Phase 2 — Claude Sonnet, guarded + highlighted
├── pipeline.py                # orchestrates Phase 1 → Phase 2 → re-verify
├── cli.py                     # `detect` / `process` command line
├── service/api.py             # FastAPI: /detect /restructure /process /config
├── n8n/                       # importable n8n workflow (HTTP → service)
├── dictionary/human_corpus.json  # 2,307 real travel sentences (Markov source)
├── skill/SKILL.md             # agent skill definition
├── tests/                     # deterministic tests (no key needed)
├── examples/                  # sample input / output / report
├── Dockerfile
└── requirements.txt
```

## Quickstart

```bash
pip install -r requirements.txt

# 1) Detection only — deterministic, free, no key:
python3 cli.py detect examples/sample_input.txt

# 2) Full run — needs Claude access:
export ANTHROPIC_API_KEY=sk-ant-...     # OR: export PB_USE_PROXY=1
python3 cli.py process examples/sample_input.txt --text-only
```

### As a service (recommended — the robust, repurposable path)

```bash
uvicorn service.api:app --host 0.0.0.0 --port 8080
# optional auth:  export PB_API_TOKEN=some-secret  (then Authorization: Bearer …)
```

| Endpoint | Body | Purpose |
|---|---|---|
| `POST /detect` | `{"text": "..."}` | Phase 1 only. Fast, deterministic, no LLM. |
| `POST /restructure` | `{"text": "...", "flagged_spans"?: [...]}` | Phase 2 only. |
| `POST /process` | `{"text": "..."}` | Full 2-phase + re-verify. The main one. |
| `GET /config` | — | The active thresholds. |
| `GET /health` | — | Status + whether Phase 2 is live. |

### n8n

Build and import the workflow:

```bash
PB_SERVICE_URL=https://your-service-host python3 n8n/build_n8n_workflow.py
# import n8n/n8n_workflow_http.json into n8n
```

The workflow only makes HTTP calls to the service, so the **same workflow drops
into any n8n instance or repo** — just point it at your service URL. If
`PB_API_TOKEN` is set, add an `Authorization: Bearer <token>` header to the HTTP
Request node.

## Configuration

Everything tunable is in `config/thresholds.json` with inline `_desc` notes.
Editing those numbers is the only supported way to change sensitivity — no logic
is hidden in code, nothing is left to model judgment.

- `PB_CLAUDE_MODEL` — Sonnet model id (default `claude-sonnet-4-6`; also
  `claude-sonnet-5`, `claude-sonnet-4-5-20250929`).
- `PB_USE_PROXY=1` — call Claude via curl (for intercepting-proxy environments).
- `ANTHROPIC_API_KEY` — direct API key (uses `requests`).

## Tests

```bash
python3 tests/test_detector.py      # or: python3 -m pytest tests/ -q
```

All tests are deterministic and need no API key or network.

## License

MIT.
