"""
Compile the four JSON dictionaries into a single JS bundle for the intake page.

Usage:
    python intake/build_intake.py

Writes:
    intake/dictionary.bundle.js
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from humanizer import Humanizer  # noqa: E402


def main() -> int:
    h = Humanizer()
    rules = h.dump_regex_rules()
    out = ROOT / "intake" / "dictionary.bundle.js"
    payload = "window.__HUMANIZER_RULES__ = " + json.dumps(rules, ensure_ascii=False) + ";\n"
    out.write_text(payload, encoding="utf-8")
    print(f"Wrote {out} with {len(rules)} rules from {len(h.loaded_dictionaries)} dictionaries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
