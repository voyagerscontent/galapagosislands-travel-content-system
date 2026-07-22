---
name: text-normalizer
description: >-
  A deterministic, hardcoded text normalization layer that cleans raw text
  before it enters a database, NLP step, or search index. It removes the
  invisible junk AI models leak - zero-width spaces, non-breaking spaces, BOMs,
  directional marks, control characters - normalizes Unicode, and standardizes
  whitespace and typographic punctuation, WITHOUT touching real letters or
  accents (José and Galápagos survive). Use this whenever the user asks to
  clean, sanitize, normalize, de-junk, or "remove weird/invisible/hidden
  characters" from text, strip zero-width or non-breaking spaces, fix
  copy-paste artifacts, or prepare text for storage/indexing. It contains NO
  LLM - it is a pure standard-library Python script, so the same input always
  produces the same output.
---

# Text Normalizer

A **hardcoded, LLM-free** normalization layer. Every transformation is an
explicit rule in `scripts/normalize.py`; there is no model, no network call,
and no randomness, so it is safe to run inside an n8n Code node, a git hook, or
a pipeline stage and trust the output byte-for-byte.

## The one rule that overrides everything

**Never delete real content in the default mode.** Zero-width spaces,
non-breaking spaces, BOMs, and control characters are noise and are removed.
Letters, accents (é, á, ñ, ö, ü), and non-Latin scripts are content and are
**preserved**. The classic `re.sub(r'[^a-zA-Z0-9\s]', '', text)` pattern is
lossy - it turns `Galápagos` into `Galpagos` and `José` into `Jos` - so it
lives ONLY behind the explicit `--aggressive` opt-in, where accents are folded
to their base letter (é -> e) rather than deleted.

## What it removes vs. keeps (default "content-safe" mode)

| Removed / normalized | Kept |
|---|---|
| Zero-width space `\u200b`, ZWNJ, ZWJ, word joiner | All letters, digits |
| Non-breaking space `\u00a0`, narrow/figure/em/en spaces -> single space | Accents & diacritics |
| BOM `\ufeff`, soft hyphen `\u00ad` | Non-Latin scripts |
| Bidi/directional format marks (LRM/RLM/overrides) | Normal punctuation `. , ! ? ; :` |
| Control characters (except `\n`) | Paragraph structure (max one blank line) |
| Smart quotes/dashes/ellipsis -> ASCII `" ' - ...` | |
| Runs of spaces -> one; trailing line whitespace | |

## Two modes

- **content-safe (default)** - for storing/displaying real content (web pages,
  CMS, docs). Cleans junk, keeps meaning. Optional `--lowercase`.
- **aggressive (`--aggressive`)** - for NLP tokens / search keys / dedup hashes.
  Folds accents to ASCII, drops all punctuation, collapses newlines, lowercases.
  Lossy by design; never use it on text you will publish.

### Respecting translation accents (protected terms)

Even in aggressive mode, proper names and non-translatable words must keep their
accents  -  `Galápagos` stays `galápagos`, not `galapagos`. Pass a protect list;
everything on it is matched accent- and case-insensitively on word boundaries
and restored with its correct accented spelling, while every other word is
transliterated normally.

```bash
python3 scripts/normalize.py --aggressive \
  --protect "Galápagos,José,Ñandú" \
  --text "tour of galapagos with jose"      # -> tour of galápagos with josé

# or from a file, one term per line
python3 scripts/normalize.py --aggressive --protect-file protected_terms.txt --file page.txt
```

```python
normalize("tour of galapagos", aggressive=True, protect=["Galápagos"])
# -> "tour of galápagos"
```

In production, load the protect list from the site's `SITE_CONFIG` (brand names,
destinations, species, people) so accents are respected per site. Content-safe
mode preserves ALL accents already and ignores the protect list.

Both modes always remove zero-width and non-breaking spaces (the two the system
cares about most).

## Workflow

### 1. Run the script (deterministic pass)

```bash
# From stdin (pipeline default)
echo "text" | python3 scripts/normalize.py

# From a file
python3 scripts/normalize.py --file input.txt

# Inline
python3 scripts/normalize.py --text "José visited Galápagos"

# Get a JSON report of exactly what was removed (for audit logs / dashboards)
python3 scripts/normalize.py --json --text "Hello​ World"

# NLP / search-key mode
python3 scripts/normalize.py --aggressive --text "Héllo   Wörld!!!"   # -> hello world
```

Flags: `--form {NFC,NFD,NFKC,NFKD}` (default NFKC), `--aggressive`,
`--lowercase`, `--no-collapse-newlines`, `--json`, `--decode-escapes`.

### 2. Import it as a function

```python
from normalize import normalize, diff_report

clean = normalize(raw_text)                       # content-safe
key   = normalize(raw_text, aggressive=True)      # search key
report = diff_report(raw_text, clean)             # what changed, counts
```

### 3. Verify

```bash
python3 scripts/test_normalize.py     # must print: ALL TESTS PASSED
```

The test suite locks in the guarantees: zero-width/NBSP removal, accent
preservation, idempotency (`normalize(normalize(x)) == normalize(x)`), and
determinism (50 identical runs).

## Guarantees (enforced by tests, do not break)

- **Deterministic** - no LLM, no network, no randomness. Same in, same out.
- **Idempotent** - safe to run repeatedly; a second pass is a no-op.
- **Content-safe by default** - accents and scripts survive; only noise leaves.
- **Zero dependencies** - Python standard library only (`re`, `unicodedata`).

## Where it fits in the pipeline

Run this as the FIRST step on any text an LLM produced or a human pasted, before
Truth Check / Humanizing / storage. It guarantees no hidden characters reach the
database, the SERP/LLM benchmarks, or the published page. See
`automation/n8n_normalize_node.json` for the drop-in n8n Code node.

## What NOT to do

- Do not use `--aggressive` on content you will publish - it strips punctuation.
- Do not add "smart" behavior that depends on context or a model - this layer's
  entire value is that it is mechanical and predictable.
- Do not change the character tables without adding a test that documents why.
