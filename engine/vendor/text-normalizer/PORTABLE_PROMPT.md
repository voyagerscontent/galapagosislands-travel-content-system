# Portable description — text-normalizer

Paste this into any agent/system that needs to understand or invoke this module.

---

**What it is:** a deterministic, hardcoded, LLM-free text normalization layer.
No model, no network, no randomness — same input always yields the same output,
and it is idempotent (running it twice changes nothing).

**What it does:** cleans raw text before storage / NLP / search indexing by
removing invisible and irregular characters and standardizing Unicode and
whitespace.

**Removes / normalizes (both modes):**
- Zero-width space `\u200b`, ZWNJ, ZWJ, word joiner, invisible math operators
- Non-breaking space `\u00a0` and all typographic spaces → single ASCII space
- BOM `\ufeff`, soft hyphen `\u00ad`, bidi/directional format marks
- Control characters (keeps `\n`)
- Unicode NFKC normalization (folds compatibility forms, e.g. fullwidth)

**Content-safe mode (default):** also maps smart quotes/dashes/ellipsis to
ASCII, collapses repeated spaces, trims, and keeps max one blank line. **Keeps
all real letters, accents, non-Latin scripts, and normal punctuation** —
`Galápagos` and `José` are preserved. Use for anything you will publish/store.

**Aggressive mode (`--aggressive`, opt-in, lossy):** for NLP tokens / search
keys / dedup hashes. Folds accents to base ASCII, drops all punctuation,
collapses newlines, lowercases. **Respects translation accents** via a protect
list: protected proper names / non-translatable words keep their accents
(`Galápagos` → `galápagos`) while everything else is transliterated
(`café` → `cafe`).

**How to call:**
```bash
python3 scripts/normalize.py [--file F | --text T | (stdin)] \
  [--form NFC|NFD|NFKC|NFKD] [--aggressive] [--lowercase] \
  [--protect "Galápagos,José"] [--protect-file terms.txt] \
  [--no-collapse-newlines] [--json]
```
```python
from normalize import normalize, diff_report
normalize(text)                                  # content-safe
normalize(text, aggressive=True, protect=[...])  # search key
diff_report(original, cleaned)                    # what changed + counts
```

**Guarantees:** deterministic, idempotent, content-safe by default, zero
dependencies (stdlib only). All enforced by `scripts/test_normalize.py`
(must print `ALL TESTS PASSED`).

**n8n:** `automation/n8n_normalize_node.json` is a drop-in Code node — the JS
twin of `normalize.py`, kept behavior-identical. Place it before any write of
LLM/pasted text.
