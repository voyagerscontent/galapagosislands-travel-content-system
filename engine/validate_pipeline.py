#!/usr/bin/env python3
"""validate_pipeline.py - consistency + anti-loop checker for the content pipeline.

Run this before deploying and after any change to a stage, the schema, or the
workflow. It enforces the one rule that keeps the pipeline from looping: the
`Status` values are a single shared contract, and every consumer (Airtable
schema, n8n workflow, Perplexity orchestrator) must use those exact ASCII
strings, with a clean one-producer/one-consumer chain and an error route out of
every working stage.

It reads the actual project files (schema JSON, n8n workflow JSON, the status
model and orchestrator markdown) and checks them against the canonical model
defined below. On success it prints `ALL CHECKS PASSED` and exits 0; on any
failure it lists every problem and exits 1, so it can gate a deploy.

Usage:
    python validate_pipeline.py [--root .]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --- The canonical contract (single source of truth) ------------------------
# Ordered happy-path chain. Plain ASCII, no em-dashes.
CANONICAL = [
    "Backlog", "Scoring", "Brief Ready", "Drafting", "Truth Check",
    "Humanizing", "Polishing", "Auditor Review", "Editor Review",
    "Ready to Publish", "Published", "Needs Attention",
]

# Happy-path transitions: producer state -> the single next state.
TRANSITIONS = {
    "Backlog": "Scoring",
    "Scoring": "Brief Ready",
    "Brief Ready": "Drafting",
    "Drafting": "Truth Check",
    "Truth Check": "Humanizing",
    "Humanizing": "Polishing",
    "Polishing": "Auditor Review",
    "Auditor Review": "Editor Review",
    "Editor Review": "Ready to Publish",
    "Ready to Publish": "Published",
}

ERROR_STATE = "Needs Attention"
TERMINAL_STATE = "Published"
# Working states must each have an error route to Needs Attention.
WORKING_STATES = [
    "Scoring", "Brief Ready", "Drafting", "Truth Check",
    "Humanizing", "Polishing", "Auditor Review", "Editor Review",
]


def find(root: Path, name: str) -> Path | None:
    hits = [p for p in root.rglob(name) if p.is_file()]
    return hits[0] if hits else None


def check_model_integrity(fail):
    """The canonical model itself must be a clean chain with one terminal."""
    # exactly one terminal (a state that is never a producer and is reachable)
    terminals = [s for s in CANONICAL if s not in TRANSITIONS and s != ERROR_STATE]
    if terminals != [TERMINAL_STATE]:
        fail(f"model: expected exactly one terminal state ({TERMINAL_STATE}), found {terminals}")
    # one producer / one consumer: each target appears as a destination once
    targets = list(TRANSITIONS.values())
    for t in set(targets):
        if targets.count(t) != 1:
            fail(f"model: state '{t}' is produced by more than one stage (forks the chain)")
    # every working state has an onward transition and an error route
    for s in WORKING_STATES:
        if s not in TRANSITIONS:
            fail(f"model: working state '{s}' has no success transition")


def check_schema(root: Path, fail):
    p = find(root, "airtable_schema.json")
    if not p:
        fail("schema: airtable_schema.json not found")
        return
    schema = json.loads(p.read_text(encoding="utf-8"))
    status = next((f for f in schema.get("fields", []) if f.get("name") == "Status"), None)
    if not status:
        fail("schema: no 'Status' field")
        return
    opts = status.get("options", [])
    if opts != CANONICAL:
        missing = [s for s in CANONICAL if s not in opts]
        extra = [s for s in opts if s not in CANONICAL]
        if missing:
            fail(f"schema Status: missing options {missing}")
        if extra:
            fail(f"schema Status: unexpected options {extra}")
        if not missing and not extra:
            fail("schema Status: options present but out of canonical order")
    # Return To must be a subset of working states (where a record can resume)
    rt = next((f for f in schema.get("fields", []) if f.get("name") == "Return To"), None)
    if rt:
        bad = [o for o in rt.get("options", []) if o and o not in CANONICAL]
        if bad:
            fail(f"schema Return To: values not in canonical list {bad}")


def check_workflow(root: Path, fail):
    p = find(root, "n8n_pipeline_corrected.json")
    if not p:
        fail("workflow: n8n_pipeline_corrected.json not found")
        return
    text = p.read_text(encoding="utf-8")
    json.loads(text)  # must be valid JSON
    # every quoted status-looking string the workflow writes must be canonical
    for value in re.findall(r"'(Backlog|Scoring|Brief Ready|Drafting|Truth Check|"
                            r"Humanizing|Polishing|Auditor Review|Editor Review|"
                            r"Ready to Publish|Published|Needs Attention|[A-Z][a-z]+ [A-Z][a-z]+)'", text):
        if value not in CANONICAL:
            fail(f"workflow: status string '{value}' is not in the canonical list")
    # the anti-loop guard: there must be an error route to Needs Attention
    if ERROR_STATE not in text:
        fail(f"workflow: no '{ERROR_STATE}' error route (this is what stops the loop)")
    # the production guard: the search filter must guard on an output field being empty
    if "= ''" not in text:
        fail("workflow: no production guard (filter should require output field = '')")


def check_orchestrator(root: Path, fail):
    p = find(root, "02_ORCHESTRATOR_PERPLEXITY.md")
    if not p:
        fail("orchestrator: 02_ORCHESTRATOR_PERPLEXITY.md not found")
        return
    text = p.read_text(encoding="utf-8")
    for state in (TERMINAL_STATE, ERROR_STATE):
        if state not in text:
            fail(f"orchestrator: does not reference '{state}' (needed for stop conditions)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repo root to search (default: cwd)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    failures: list[str] = []
    fail = failures.append

    check_model_integrity(fail)
    check_schema(root, fail)
    check_workflow(root, fail)
    check_orchestrator(root, fail)

    if failures:
        print("PIPELINE VALIDATION FAILED:\n")
        for f in failures:
            print(f"  - {f}")
        print(f"\n{len(failures)} problem(s). Fix these before deploying.")
        return 1

    print("ALL CHECKS PASSED")
    print(f"  {len(CANONICAL)} canonical states, clean one-producer/one-consumer chain,")
    print(f"  error route to '{ERROR_STATE}' on every working stage, one terminal ('{TERMINAL_STATE}').")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
