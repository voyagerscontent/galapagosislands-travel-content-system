"""
Top-level orchestrator tying Phase 1 (detect) and Phase 2 (restructure) together,
plus the deterministic acceptance re-test.

    process(text) ->
        1. detect(text)                      # Phase 1
        2. if not flagged: return unchanged
        3. restructure(text, spans)          # Phase 2 (Claude, guarded)
        4. detect(output)                    # re-test: did we clear the flags?
        5. return full report

Import this from the CLI and the FastAPI service.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Dict, Optional

from detector.detector import detect
from restructurer.restructure import restructure


def process(text: str, config_path: Optional[str] = None, max_passes: int = 3,
            temperature: float = 0.4) -> Dict:
    phase1 = detect(text, config_path=config_path)

    result: Dict = {
        "input_word_count": phase1.word_count,
        "phase1": phase1.to_dict(),
        "phase2": None,
        "phase1_recheck": None,
        "final_text": text,
        "final_html": None,
        "changed": False,
        "needs_human_review": False,
        "flags_cleared": None,
    }

    if not phase1.flagged:
        result["note"] = "No mechanical patterns detected. Text left unchanged."
        return result

    # Load the convergence budget from config.
    import json as _json
    from pathlib import Path as _Path
    cfg_p = _Path(config_path) if config_path else (
        _Path(__file__).resolve().parent / "config" / "thresholds.json")
    verify_passes = _json.loads(cfg_p.read_text())["engine"]["verify_max_passes"]

    def _strip(t: str) -> str:
        return t.replace("[[PB-REVIEW]]", "").replace("[[/PB-REVIEW]]", "")

    working = text
    current_report = phase1
    last_phase2 = None
    rounds = []
    for _round in range(1, verify_passes + 1):
        phase2 = restructure(working, current_report.flagged_spans,
                             max_passes=max_passes, temperature=temperature)
        last_phase2 = phase2
        clean_out = _strip(phase2.output_text)
        recheck = detect(clean_out, config_path=config_path)
        rounds.append({
            "round": _round,
            "still_flagged": recheck.flagged,
            "factors": sorted({f.factor for f in recheck.flags}),
            "metrics": recheck.metrics,
        })
        # In dry-run nothing changes; stop after one round.
        if phase2.dry_run or not recheck.flagged:
            current_report = recheck
            working = phase2.output_text  # keep highlights on final round
            break
        # else iterate on the cleaned text against the new flags
        working = clean_out
        current_report = recheck

    final_recheck = detect(_strip(last_phase2.output_text), config_path=config_path)
    result["phase2"] = last_phase2.to_dict()
    result["phase1_recheck"] = final_recheck.to_dict()
    result["rounds"] = rounds
    result["final_text"] = last_phase2.output_text
    result["final_html"] = last_phase2.output_html
    result["changed"] = not last_phase2.dry_run
    result["needs_human_review"] = last_phase2.needs_human_review
    result["flags_cleared"] = (not final_recheck.flagged) if not last_phase2.dry_run else None
    return result


if __name__ == "__main__":
    import sys
    src = sys.stdin.read() if not sys.argv[1:] else open(sys.argv[1]).read()
    print(json.dumps(process(src), indent=2))
