#!/usr/bin/env python3
"""
Command-line interface for the pattern-breaker.

Usage:
    # Phase 1 only (deterministic, no LLM, no key needed):
    python3 cli.py detect  input.txt
    echo "some text" | python3 cli.py detect

    # Full 2-phase run (needs Claude access):
    export PB_USE_PROXY=1                # behind credential proxy
    #   or  export ANTHROPIC_API_KEY=... # direct key
    python3 cli.py process input.txt -o out.json
    python3 cli.py process input.txt --text-only     # print final rewrite only

Flags:
    --config PATH     use an alternate thresholds file
    --max-passes N    Claude re-prompt attempts per span (default 3)
    --temperature T   Claude temperature (default 0.4)
    -o, --out PATH    write full JSON result to a file
    --text-only       (process) print only the final rewritten text
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from detector.detector import detect
from pipeline import process


def _read(src: str | None) -> str:
    if src and src != "-":
        return Path(src).read_text(encoding="utf-8")
    return sys.stdin.read()


def main() -> int:
    ap = argparse.ArgumentParser(description="Two-phase AI-pattern breaker.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("detect", help="Phase 1 only (deterministic).")
    d.add_argument("input", nargs="?", help="input file (or stdin)")
    d.add_argument("--config", default=None)
    d.add_argument("-o", "--out", default=None)

    p = sub.add_parser("process", help="Full 2-phase run.")
    p.add_argument("input", nargs="?", help="input file (or stdin)")
    p.add_argument("--config", default=None)
    p.add_argument("--max-passes", type=int, default=3)
    p.add_argument("--temperature", type=float, default=0.4)
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--text-only", action="store_true")

    args = ap.parse_args()
    text = _read(args.input)

    if args.cmd == "detect":
        result = detect(text, config_path=args.config).to_dict()
        out = json.dumps(result, indent=2)
    else:
        result = process(text, config_path=args.config,
                         max_passes=args.max_passes, temperature=args.temperature)
        if args.text_only:
            print(result["final_text"])
            return 0
        out = json.dumps(result, indent=2)

    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
