"""
Compile the dictionaries + context triggers into a single JS bundle for the
intake page.

v1.4 adds `window.__HUMANIZER_TRIGGERS__` so the intake page can display
flagged spans as inline highlights with variant tooltips. LLM rewrite from
the intake page is OPTIONAL — if the user pastes an OpenAI API key into the
form the browser calls api.openai.com directly; otherwise the page runs in
flag-only display mode.

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
    triggers = h.dump_triggers()
    out = ROOT / "intake" / "dictionary.bundle.js"
    payload = (
        "window.__HUMANIZER_RULES__ = "
        + json.dumps(rules, ensure_ascii=False)
        + ";\n"
        + "window.__HUMANIZER_TRIGGERS__ = "
        + json.dumps(triggers, ensure_ascii=False)
        + ";\n"
    )
    out.write_text(payload, encoding="utf-8")
    print(
        f"Wrote {out} with {len(rules)} regex rules and {len(triggers)} "
        f"context triggers from {len(h.loaded_dictionaries)} dictionaries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
