#!/usr/bin/env python3
"""
Deterministic tests for the text normalization layer.

Run: python3 test_normalize.py
No third-party test framework needed  -  pure stdlib assertions so it runs
anywhere (CI, n8n sidecar, local) with a clean exit code.
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from normalize import normalize, diff_report  # noqa: E402

FAILS = []


def check(name, got, expected):
    if got != expected:
        FAILS.append(f"{name}\n    expected: {expected!r}\n    got:      {got!r}")
    else:
        print(f"  ok  {name}")


# --- The two explicitly requested behaviors --------------------------------

# Zero-width space is deleted entirely (no leftover space).
check("zero-width space removed",
      normalize("Hello\u200bWorld"), "HelloWorld")

# Non-breaking space becomes a normal space.
check("non-breaking space -> normal space",
      normalize("Hello\u00a0World"), "Hello World")

# BOM / zero-width no-break space removed.
check("BOM removed",
      normalize("\ufeffHello"), "Hello")

# Soft hyphen removed.
check("soft hyphen removed",
      normalize("co\u00adoperate"), "cooperate")

# Word joiner and directional marks removed.
check("word joiner + LRM removed",
      normalize("a\u2060b\u200ec"), "abc")


# --- Content safety: accents and non-Latin scripts survive ------------------

check("Spanish accents preserved",
      normalize("Galápagos"), "Galápagos")

check("name accent preserved",
      normalize("José María"), "José María")

# NFKC still folds compatibility forms (fullwidth) but keeps real letters.
check("fullwidth folded to ASCII",
      normalize("ＨＥＬＬＯ"), "HELLO")

# Combining accent gets composed (NFKC) but the letter+accent survives.
check("decomposed accent composed, preserved",
      normalize("Cafe\u0301"), "Café")


# --- Whitespace + punctuation standardization -------------------------------

check("collapse multiple spaces",
      normalize("a     b"), "a b")

check("trim leading/trailing",
      normalize("   hi   "), "hi")

check("tabs become spaces and collapse",
      normalize("a\t\t b"), "a b")

check("smart quotes -> ascii",
      normalize("\u201cquote\u201d and \u2019s"), '"quote" and \'s')

check("em dash -> hyphen",
      normalize("a \u2014 b"), "a - b")

check("ellipsis -> three dots",
      normalize("wait\u2026"), "wait...")

check("paragraphs preserved, triple newline collapsed",
      normalize("p1\n\n\n\np2"), "p1\n\np2")

check("CRLF normalized",
      normalize("a\r\nb"), "a\nb")


# --- Aggressive (NLP/search) mode -------------------------------------------

check("aggressive strips punctuation + lowercases",
      normalize("Héllo   Wörld!!!\u200b \n\n", aggressive=True), "hello world")

check("aggressive removes NBSP too",
      normalize("Hello\u00a0World!", aggressive=True), "hello world")

check("aggressive removes zero-width too",
      normalize("data\u200bpoint", aggressive=True), "datapoint")


# --- Aggressive mode WITH protected names / non-translatable terms ----------

# Protected accented name keeps its accent; the rest is transliterated.
check("protected name keeps accent, rest folded",
      normalize("Visit Gal\u00e1pagos with Jos\u00e9 caf\u00e9", aggressive=True,
                protect=["Gal\u00e1pagos", "Jos\u00e9"]),
      "visit gal\u00e1pagos with jos\u00e9 cafe")

# Match is accent-insensitive: source without accent still gets the accent back.
check("protect matches unaccented source, restores accent",
      normalize("tour of galapagos", aggressive=True, protect=["Gal\u00e1pagos"]),
      "tour of gal\u00e1pagos")

# Match is case-insensitive.
check("protect is case-insensitive",
      normalize("GALAPAGOS islands", aggressive=True, protect=["Gal\u00e1pagos"]),
      "gal\u00e1pagos islands")

# Word-boundary: does not touch substrings inside larger words.
check("protect respects word boundaries",
      normalize("galapagosislands", aggressive=True, protect=["Gal\u00e1pagos"]),
      "galapagosislands")

# Multiple protected terms including ñ.
check("multiple protected terms incl \u00f1",
      normalize("the \u00d1and\u00fa near Gal\u00e1pagos", aggressive=True,
                protect=["\u00d1and\u00fa", "Gal\u00e1pagos"]),
      "the \u00f1and\u00fa near gal\u00e1pagos")

# Idempotent with protect.
_p = ["Gal\u00e1pagos", "Jos\u00e9"]
_once = normalize("Jos\u00e9 at galapagos!!!", aggressive=True, protect=_p)
check("idempotent aggressive+protect",
      normalize(_once, aggressive=True, protect=_p), _once)


# --- Idempotency (critical invariant) ---------------------------------------

samples = [
    "Héllo\u200b   Wörld!!!\r\n\n\n",
    "José\u00a0visited Galápagos \u2014 in 2019\u2026",
    "\ufeff  mixed\ttabs and\u2003em-space ",
    "line1\r\nline2\u2028line3",
]
for i, s in enumerate(samples):
    once = normalize(s)
    twice = normalize(once)
    check(f"idempotent content-safe [{i}]", twice, once)

    once_a = normalize(s, aggressive=True)
    twice_a = normalize(once_a, aggressive=True)
    check(f"idempotent aggressive [{i}]", twice_a, once_a)


# --- Determinism (same input, repeated) -------------------------------------

s = "Repeat\u00a0me\u200b please  —  José"
results = {normalize(s) for _ in range(50)}
check("deterministic (50 runs identical)", len(results), 1)


# --- Edge cases -------------------------------------------------------------

check("empty string", normalize(""), "")
check("None -> empty", normalize(None), "")
check("only invisibles -> empty", normalize("\u200b\ufeff\u00ad"), "")
check("only whitespace -> empty", normalize("   \n\t  "), "")
check("integer coerced", normalize(12345), "12345")


# --- diff_report accounting -------------------------------------------------

r = diff_report("a\u200b\u200bb\u00a0c", normalize("a\u200b\u200bb\u00a0c"))
check("report counts zero-width", r["zero_width_removed"], 2)
check("report counts nbsp", r["non_breaking_spaces_removed"], 1)
check("report changed flag", r["changed"], True)


# --- Shared fixtures (same file the JS sync test reads) ---------------------
# Guarantees the Python side agrees with the exact inputs/outputs the n8n JS
# twin is checked against, so the two implementations cannot silently diverge.

with open(os.path.join(_HERE, "fixtures.json"), encoding="utf-8") as _fh:
    _fx = json.load(_fh)

for _f in _fx["content_safe"]:
    check(f"[fixture content-safe] {_f['name']}", normalize(_f["in"]), _f["out"])

for _f in _fx["aggressive"]:
    check(f"[fixture aggressive] {_f['name']}",
          normalize(_f["in"], aggressive=True, protect=_fx["protect"]),
          _f["out"])


# --- Summary ----------------------------------------------------------------

print()
if FAILS:
    print(f"FAILED {len(FAILS)} test(s):\n")
    for f in FAILS:
        print("  X  " + f)
    sys.exit(1)
print("ALL TESTS PASSED")
sys.exit(0)
