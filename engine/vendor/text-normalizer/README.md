# text-normalizer

![CI](https://github.com/voyagerscontent/text-normalizer/actions/workflows/ci.yml/badge.svg)

A **deterministic, hardcoded, LLM-free** text normalization layer. It cleans raw
text before it enters a database, NLP step, or search index by removing the
invisible junk AI models leak and standardizing Unicode, whitespace, and
typographic punctuation — **without destroying real content**.

This is a standalone, self-contained repo designed to be pushed into larger
systems (e.g. `voyagerscontent/Weboptimizer`) as a read-only imported module,
exactly like `code-reviewer` and `content-system`.

## Why it exists

AI models routinely emit **zero-width spaces** (`\u200b`), **non-breaking
spaces** (`\u00a0`), BOMs, directional marks, and control characters that are
invisible on screen but corrupt search, diffing, dedup, and storage. This layer
strips all of them — deterministically, with no model in the loop, so the same
input always produces the same output and running it twice is a no-op.

## The core guarantee: content-safe by default

The naive `re.sub(r'[^a-zA-Z0-9\s]', '', text)` pattern is lossy — it turns
`Galápagos` into `Galpagos` and `José` into `Jos`. This layer does **not** do
that by default. Default (content-safe) mode:

- **Removes:** zero-width spaces, non-breaking/typographic spaces (→ one space),
  BOM, soft hyphen, bidi/directional marks, control characters, and maps smart
  quotes/dashes/ellipsis to ASCII.
- **Keeps:** every letter, digit, accent (é, á, ñ, ö, ü), non-Latin script,
  normal punctuation, and paragraph structure.

## Two modes

| Mode | Use for | Accents | Punctuation |
|---|---|---|---|
| `content-safe` (default) | Publishing, CMS, storage, display | **Preserved** | Preserved (smart → ASCII) |
| `aggressive` (`--aggressive`) | NLP tokens, search keys, dedup hashes | Folded to ASCII* | Dropped, lowercased |

\*Aggressive mode **respects translation accents** for protected terms: proper
names and non-translatable words on a protect list keep their accents
(`Galápagos` → `galápagos`), while every other word is transliterated
(`café` → `cafe`). See `--protect` / `--protect-file`.

Both modes always remove zero-width and non-breaking spaces.

## Quick start

```bash
# clean from stdin (pipeline default) — accents preserved
echo "José visited Galápagos" | python3 .claude/skills/text-normalizer/scripts/normalize.py

# JSON report of exactly what was removed
python3 .claude/skills/text-normalizer/scripts/normalize.py --json --text "Hello​ World"

# search key, respecting protected accented names
python3 .claude/skills/text-normalizer/scripts/normalize.py --aggressive \
  --protect "Galápagos,José,Ñandú" --text "tour of galapagos with jose"
# -> tour of galápagos with josé

# run the tests
python3 .claude/skills/text-normalizer/scripts/test_normalize.py   # -> ALL TESTS PASSED
```

Import as a library:

```python
from normalize import normalize, diff_report
clean  = normalize(raw)                                  # content-safe
key    = normalize(raw, aggressive=True, protect=["Galápagos"])
report = diff_report(raw, clean)
```

## Guarantees (locked by `test_normalize.py`)

- **Deterministic** — no LLM, no network, no randomness.
- **Idempotent** — `normalize(normalize(x)) == normalize(x)`.
- **Content-safe by default** — accents and scripts survive.
- **Zero dependencies** — Python standard library only.

## Repo layout

```
.claude/skills/text-normalizer/          installable Agent Skill (single source of truth)
  SKILL.md                               skill instructions + workflow
  scripts/normalize.py                   the hardcoded normalizer (CLI + importable)
  scripts/test_normalize.py              deterministic test suite (no framework)
  scripts/sync_test.js                   JS<->Python parity test for the n8n twin
  scripts/fixtures.json                  shared inputs/outputs both tests check against
  automation/n8n_normalize_node.json     drop-in n8n Code node (JS twin, no LLM)
  protected_terms.example.txt            sample --protect-file
.github/workflows/ci.yml                 runs both test suites on every push/PR
README.md
PORTABLE_PROMPT.md                       one-paste description for any agent
```

## Using it inside another system (n8n)

Drop `automation/n8n_normalize_node.json` at the **top** of any stage that
receives LLM-generated or pasted text (before it is stored or benchmarked). It
is a pure Code node — the exact JavaScript twin of `normalize.py`, same
character tables, same order — so no hidden character ever reaches your database
or published page. Set `MODE` and the `PROTECT` list per site. Prefer Python?
Swap it for an Execute Command node calling `normalize.py` — identical output.

## Keeping the two twins in sync

`normalize.py` (Python) and the JS inside `n8n_normalize_node.json` must stay
behavior-identical. This is enforced automatically:

- `scripts/fixtures.json` is the shared source of truth — a set of inputs with
  their expected outputs for both modes.
- `test_normalize.py` checks the Python implementation against those fixtures.
- `sync_test.js` extracts the JavaScript embedded in the n8n node, runs the
  same fixtures through it, verifies the node's `PROTECT` list matches, and
  cross-checks that the JS output is **byte-identical to `normalize.py`** for
  every input.
- **CI** (`.github/workflows/ci.yml`) runs both on every push and pull request,
  so any drift between the two twins fails the build.

```bash
python3 .claude/skills/text-normalizer/scripts/test_normalize.py   # -> ALL TESTS PASSED
node    .claude/skills/text-normalizer/scripts/sync_test.js        # -> SYNC OK
```
