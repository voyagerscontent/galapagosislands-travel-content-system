"""
CLI: python -m humanizer.cli --input file.txt --output out.txt --json report.json
     echo "text" | python -m humanizer.cli
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import Humanizer


def main() -> int:
    p = argparse.ArgumentParser(description="Deterministic AI-quirk humanizer for travel copy.")
    p.add_argument("--input", "-i", help="Input text file (utf-8). If omitted, reads stdin.")
    p.add_argument("--output", "-o", help="Write humanized text to this file. Defaults to stdout.")
    p.add_argument("--json", dest="json_report", help="Write JSON report to this file.")
    p.add_argument("--max-words", type=int, default=3000, help="Word cap (default 3000).")
    p.add_argument("--dict-dir", help="Custom dictionary directory.")
    p.add_argument("--dicts", nargs="+", help="Custom ordered list of dictionary filenames.")
    args = p.parse_args()

    if args.input:
        text = Path(args.input).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    h = Humanizer(
        dictionaries=args.dicts,
        dict_dir=Path(args.dict_dir) if args.dict_dir else None,
        max_words=args.max_words,
    )
    result = h.humanize(text)

    if args.output:
        Path(args.output).write_text(result.text, encoding="utf-8")
    else:
        sys.stdout.write(result.text)
        if not result.text.endswith("\n"):
            sys.stdout.write("\n")

    if args.json_report:
        Path(args.json_report).write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # Human-friendly stats to stderr
    sys.stderr.write(
        f"[humanizer] words={result.word_count} "
        f"replacements={result.replacement_count} "
        f"truncated={result.truncated} "
        f"dicts={h.loaded_dictionaries}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
