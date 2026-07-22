#!/usr/bin/env python3
"""
Text Normalization Layer  -  deterministic, hardcoded, NO LLM.

Cleans raw text by removing irregular / invisible characters, normalizing
Unicode, and standardizing whitespace. Built for content pipelines, databases,
NLP steps and search indexing.

Design rules (do not "improve" into behavior changes):
  * 100% deterministic. Same input -> same output, always. No model, no network,
    no randomness. Safe to run inside an n8n Code node or a git-tracked script.
  * Idempotent. normalize(normalize(x)) == normalize(x).
  * Content-safe by DEFAULT. It strips the junk AI models leak
    (zero-width spaces, non-breaking spaces, BOMs, control chars, smart quotes)
    but PRESERVES real letters, accents and punctuation, so "Galápagos" and
    "José" survive. This is the mode a travel/content system wants.
  * An explicit --aggressive mode reproduces the classic "alnum + space only,
    lowercased" reduction for NLP tokenization / search keys. Opt-in only,
    because it is lossy (it deletes accents and punctuation).

The two things the user specifically asked for  -  removing zero-width spaces
and non-breaking spaces  -  happen in BOTH modes and are covered by the tests.

Usage:
  echo "text"           | python3 normalize.py
  python3 normalize.py --file input.txt
  python3 normalize.py --text "Héllo\u200b Wörld"
  python3 normalize.py --aggressive --text "Héllo   Wörld!!!"
  python3 normalize.py --json --text "..."      # structured report of what changed

No third-party dependencies  -  standard library only (re, unicodedata).
"""

import argparse
import json
import re
import sys
import unicodedata

# ---------------------------------------------------------------------------
# Explicit character tables. Hardcoded on purpose so nothing is guessed at
# runtime. Every codepoint here is documented.
# ---------------------------------------------------------------------------

# Invisible / zero-width characters that carry no meaning and are almost always
# an artifact (AI output, copy-paste from web/office, tracking pixels in text).
# These are DELETED (mapped to nothing).
ZERO_WIDTH = {
    "\u200b",  # ZERO WIDTH SPACE          <- explicitly requested
    "\u200c",  # ZERO WIDTH NON-JOINER
    "\u200d",  # ZERO WIDTH JOINER
    "\u2060",  # WORD JOINER
    "\ufeff",  # ZERO WIDTH NO-BREAK SPACE / BOM
    "\u180e",  # MONGOLIAN VOWEL SEPARATOR
    "\u00ad",  # SOFT HYPHEN (invisible unless line-wrapped)
    "\u200e",  # LEFT-TO-RIGHT MARK
    "\u200f",  # RIGHT-TO-LEFT MARK
    "\u202a",  # LEFT-TO-RIGHT EMBEDDING
    "\u202b",  # RIGHT-TO-LEFT EMBEDDING
    "\u202c",  # POP DIRECTIONAL FORMATTING
    "\u202d",  # LEFT-TO-RIGHT OVERRIDE
    "\u202e",  # RIGHT-TO-LEFT OVERRIDE
    "\u2061",  # FUNCTION APPLICATION
    "\u2062",  # INVISIBLE TIMES
    "\u2063",  # INVISIBLE SEPARATOR
    "\u2064",  # INVISIBLE PLUS
}

# Whitespace-like characters that should collapse to a normal ASCII space " ".
# Non-breaking spaces are the headline case  <- explicitly requested.
UNICODE_SPACES = {
    "\u00a0",  # NO-BREAK SPACE            <- explicitly requested
    "\u2007",  # FIGURE SPACE
    "\u202f",  # NARROW NO-BREAK SPACE
    "\u2000",  # EN QUAD
    "\u2001",  # EM QUAD
    "\u2002",  # EN SPACE
    "\u2003",  # EM SPACE
    "\u2004",  # THREE-PER-EM SPACE
    "\u2005",  # FOUR-PER-EM SPACE
    "\u2006",  # SIX-PER-EM SPACE
    "\u2008",  # PUNCTUATION SPACE
    "\u2009",  # THIN SPACE
    "\u200a",  # HAIR SPACE
    "\u205f",  # MEDIUM MATHEMATICAL SPACE
    "\u3000",  # IDEOGRAPHIC SPACE
    "\u1680",  # OGHAM SPACE MARK
    "\t",      # TAB
    "\v",      # VERTICAL TAB
    "\f",      # FORM FEED
}

# "Smart" / typographic punctuation -> plain ASCII equivalents. Applied in
# content-safe mode so quotes and dashes are consistent without destroying them.
PUNCT_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",  # single quotes
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',  # double quotes
    "\u2032": "'", "\u2033": '"',                                  # primes
    "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2212": "-",   # dashes / minus
    "\u2010": "-", "\u2011": "-",                                  # hyphens
    "\u2026": "...",                                               # ellipsis
    "\u00ab": '"', "\u00bb": '"',                                  # guillemets
    "\u2044": "/",                                                 # fraction slash
}

# Line separators normalized to \n before whitespace collapse.
LINE_SEPARATORS = {
    "\u2028": "\n",  # LINE SEPARATOR
    "\u2029": "\n",  # PARAGRAPH SEPARATOR
    "\r\n": "\n",
    "\r": "\n",
}

_ZERO_WIDTH_RE = re.compile("[" + "".join(re.escape(c) for c in ZERO_WIDTH) + "]")
_UNICODE_SPACE_RE = re.compile("[" + "".join(re.escape(c) for c in UNICODE_SPACES) + "]")
# Control characters (Cc) except \n and \t; \t is handled as whitespace above.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Collapse runs of horizontal spaces (not newlines) to a single space.
_MULTISPACE_RE = re.compile(r"[ ]{2,}")
# Collapse 3+ newlines to a paragraph break (max two).
_MULTINEWLINE_RE = re.compile(r"\n{3,}")
# Trailing horizontal whitespace at end of each line.
_TRAILING_WS_RE = re.compile(r"[ \t]+(?=\n)")
# Aggressive mode: keep only ASCII letters, digits and whitespace.
_AGGRESSIVE_RE = re.compile(r"[^a-zA-Z0-9\s]")


def _apply_map(text, mapping):
    for src, dst in mapping.items():
        if src in text:
            text = text.replace(src, dst)
    return text


def _fold_accents(text):
    """Decompose (NFKD) and drop combining marks: é -> e, ö -> o, ñ -> n."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalize(
    text,
    *,
    form="NFKC",
    aggressive=False,
    lowercase=False,
    collapse_newlines=True,
    protect=None,
):
    """
    Return a cleaned copy of `text`.

    Content-safe mode (default) pipeline:
      1. Unicode normalize (NFKC by default; folds compatibility forms).
      2. Delete zero-width / invisible / directional-format characters.
      3. Delete control characters (keep \\n and \\t; \\t becomes a space next).
      4. Map Unicode/typographic spaces -> ASCII space; line seps -> \\n.
      5. Map smart quotes/dashes/ellipsis -> ASCII equivalents.
      6. Collapse repeated spaces, trim trailing line whitespace, collapse
         3+ blank lines to one blank line, strip document ends.

    Aggressive mode adds (for NLP/search keys, lossy):
      7. Delete everything except ASCII [a-zA-Z0-9] and whitespace.
      8. Collapse ALL whitespace (including newlines) to single spaces.
      + lowercase forced on.

    `form` is any valid unicodedata form: NFC, NFD, NFKC, NFKD.

    `protect` (aggressive mode only) is an iterable of accented terms whose
    accents MUST survive even in the lossy pass  -  proper names and
    non-translatable words (e.g. "Galápagos", "José", "Ñandú"). Matching is
    case-insensitive and accent-insensitive on word boundaries; the ORIGINAL
    accented spelling is restored (still lowercased). Everything not protected
    is transliterated to ASCII as usual. This is how the layer "respects
    translation accents for names and words that are not translatable but
    transliterates" the rest.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    # 1. Unicode normalization.
    text = unicodedata.normalize(form, text)

    # 2. Zero-width / invisible / bidi-format characters -> gone.
    text = _ZERO_WIDTH_RE.sub("", text)

    # 3. Control characters -> gone (newline and tab preserved).
    text = _CONTROL_RE.sub("", text)

    # 4. Unicode spaces -> ASCII space; line separators -> \n.
    text = _apply_map(text, LINE_SEPARATORS)
    text = _UNICODE_SPACE_RE.sub(" ", text)

    if aggressive:
        # 7a. Fold every accent to its base ASCII letter (é -> e), keeping words
        #     intact for tokenization instead of losing whole letters.
        folded = _fold_accents(text)
        # 7b. Restore accents ONLY for protected names / non-translatable terms.
        #     We match on the FOLDED text (accent- and case-insensitive) and
        #     substitute back the original accented, lowercased spelling. This
        #     is what "respect accents for names/untranslatable words but
        #     transliterate the rest" means in the lossy pass.
        if protect:
            placeholders = {}
            for i, term in enumerate(dict.fromkeys(t for t in protect if t and t.strip())):
                token = f"\x00P{i}\x00"
                pat = re.compile(r"(?<!\w)" + re.escape(_fold_accents(term)) + r"(?!\w)",
                                 re.IGNORECASE)
                folded = pat.sub(token, folded)
                placeholders[token] = term.lower()
            text = folded
            # 7c. Strip non-ASCII-alnum noise (keep the \x00 placeholders).
            text = re.sub(r"[^a-zA-Z0-9\s\x00]", "", text)
            for token, original_lower in placeholders.items():
                text = text.replace(token, original_lower)
        else:
            text = re.sub(r"[^a-zA-Z0-9\s]", "", folded)
        # 8. All whitespace -> single space.
        text = re.sub(r"\s+", " ", text)
        return text.strip().lower()

    # 5. Typographic punctuation -> ASCII.
    text = _apply_map(text, PUNCT_MAP)

    # 6. Whitespace standardization (structure-preserving).
    text = _MULTISPACE_RE.sub(" ", text)
    text = _TRAILING_WS_RE.sub("", text)
    if collapse_newlines:
        text = _MULTINEWLINE_RE.sub("\n\n", text)
    else:
        text = text.replace("\n", " ")
        text = _MULTISPACE_RE.sub(" ", text)

    text = text.strip()
    if lowercase:
        text = text.lower()
    return text


def diff_report(original, cleaned):
    """Structured, deterministic report of what the cleaner removed/changed."""
    removed_zero_width = sum(original.count(c) for c in ZERO_WIDTH)
    removed_nbsp = original.count("\u00a0")
    removed_unicode_spaces = sum(original.count(c) for c in UNICODE_SPACES)
    removed_controls = len(_CONTROL_RE.findall(original))
    smart_punct = sum(original.count(c) for c in PUNCT_MAP)
    return {
        "changed": original != cleaned,
        "original_length": len(original),
        "cleaned_length": len(cleaned),
        "zero_width_removed": removed_zero_width,
        "non_breaking_spaces_removed": removed_nbsp,
        "unicode_spaces_normalized": removed_unicode_spaces,
        "control_chars_removed": removed_controls,
        "smart_punctuation_mapped": smart_punct,
        "cleaned": cleaned,
    }


def _read_input(args):
    if args.text is not None:
        # Allow literal escape sequences on the CLI (e.g. \u200b) to be useful.
        return args.text.encode("utf-8").decode("unicode_escape") if args.decode_escapes else args.text
    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            return fh.read()
    return sys.stdin.read()


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Deterministic text normalization layer (no LLM).",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--text", help="Text to normalize (else reads a --file or stdin).")
    src.add_argument("--file", help="Path to a UTF-8 text file to normalize.")
    p.add_argument("--form", default="NFKC", choices=["NFC", "NFD", "NFKC", "NFKD"],
                   help="Unicode normalization form (default NFKC).")
    p.add_argument("--aggressive", action="store_true",
                   help="Lossy: keep only ASCII alnum + spaces, lowercase. For NLP/search keys.")
    p.add_argument("--protect", default=None,
                   help="Comma-separated accented names/terms to keep accented even in "
                        "--aggressive mode (e.g. 'Galápagos,José,Ñandú'). Or use --protect-file.")
    p.add_argument("--protect-file", default=None,
                   help="Path to a UTF-8 file with one protected term per line.")
    p.add_argument("--lowercase", action="store_true",
                   help="Lowercase output (content-safe mode; --aggressive already lowercases).")
    p.add_argument("--no-collapse-newlines", dest="collapse_newlines", action="store_false",
                   help="Flatten all newlines to spaces instead of preserving paragraphs.")
    p.add_argument("--json", action="store_true",
                   help="Emit a JSON report of what was removed/changed instead of raw text.")
    p.add_argument("--decode-escapes", action="store_true",
                   help="Interpret literal escapes like \\u200b in --text (for quick testing).")
    args = p.parse_args(argv)

    protect = []
    if args.protect:
        protect += [t.strip() for t in args.protect.split(",") if t.strip()]
    if args.protect_file:
        with open(args.protect_file, "r", encoding="utf-8") as fh:
            protect += [ln.strip() for ln in fh if ln.strip()]

    original = _read_input(args)
    cleaned = normalize(
        original,
        form=args.form,
        aggressive=args.aggressive,
        lowercase=args.lowercase,
        collapse_newlines=args.collapse_newlines,
        protect=protect or None,
    )

    if args.json:
        report = diff_report(original, cleaned)
        report["mode"] = "aggressive" if args.aggressive else "content-safe"
        report["form"] = args.form
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(cleaned)
        if not args.json and (not cleaned.endswith("\n")):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
