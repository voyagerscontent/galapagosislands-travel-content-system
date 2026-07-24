#!/usr/bin/env python3
"""code-scientist: a language-agnostic static hygiene reviewer.

Philosophy
----------
This script does the *deterministic, boring* half of a code review so the agent
(and the human) can spend judgment on the parts that need it. It is READ-ONLY by
default: it reports problems, it does not rewrite your logic. The optional --fix
flag performs only behavior-preserving cleanups (whitespace, blank lines, final
newline). It will never touch your comments, debug statements, or actual code,
because deciding whether those should go requires understanding intent.

Findings are tagged by severity so they can be triaged and used in CI:
    error  - almost certainly broken or unmergeable (e.g. merge-conflict markers)
    warn   - likely a mistake or leftover (debug prints, trailing whitespace)
    info   - hygiene / fluff worth a human glance (TODOs, long lines, dead code)

Exit code is 0 unless findings reach the --fail-on threshold (default: error),
so this can gate a pull request without being noisy.

Usage
-----
    python review.py PATH [PATH ...]
    python review.py . --json
    python review.py src/ --max-line-length 100 --fail-on warn
    python review.py . --fix              # safe cleanups, in place
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Directories that are never the author's own source and only add noise.
EXCLUDE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "venv", ".venv", "env", ".env",
    "dist", "build", "target", ".idea", ".vscode", "vendor", ".next",
    "coverage", ".tox", ".gradle", "bin", "obj",
}

# Debug / leftover statements across common languages. Flagged, never deleted:
# only the author knows whether a given print is intentional.
DEBUG_PATTERNS = [
    (re.compile(r"\bconsole\.(log|debug|trace)\s*\("), "console.log"),
    (re.compile(r"\bdebugger\b"), "debugger statement"),
    (re.compile(r"\bprint\s*\("), "print()"),
    (re.compile(r"\bpprint\s*\("), "pprint()"),
    (re.compile(r"\bSystem\.out\.print"), "System.out.print"),
    (re.compile(r"\bfmt\.Print"), "fmt.Print"),
    (re.compile(r"\bvar_dump\s*\("), "var_dump()"),
    (re.compile(r"\bdd\s*\("), "dd()"),
    (re.compile(r"\bbinding\.pry\b"), "binding.pry"),
    (re.compile(r"\bbyebug\b"), "byebug"),
]

TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK|BUG)\b")
CONFLICT_RE = re.compile(r"^(<{7}|={7}|>{7})(\s|$)")

# Conservative "this comment looks like commented-out code" heuristic. We only
# fire when a comment body contains code-shaped punctuation, to avoid flagging
# ordinary prose comments.
COMMENT_PREFIX_RE = re.compile(r"^\s*(#|//|--)\s?(.*)$")
CODE_SHAPE_RE = re.compile(r"[;{}]\s*$|=\s*\S|\)\s*[:{]?\s*$|\b(if|for|while|return|def|function|var|let|const)\b\s*\(")


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    code: str
    message: str


@dataclass
class FixResult:
    file: str
    changes: list[str] = field(default_factory=list)


def is_probably_binary(path: Path) -> bool:
    """A NUL byte in the first chunk is a reliable, dependency-free binary signal."""
    try:
        with path.open("rb") as fh:
            return b"\x00" in fh.read(4096)
    except OSError:
        return True


def iter_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in EXCLUDE_DIRS for part in path.parts):
                continue
            files.append(path)
    return files


def analyze_file(path: Path, max_line_length: int, large_file_lines: int) -> list[Finding]:
    findings: list[Finding] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings  # unreadable / non-text: skip silently

    lines = raw.splitlines()
    name = str(path)

    if len(lines) > large_file_lines:
        findings.append(Finding(name, len(lines), "info", "large-file",
                                 f"file is {len(lines)} lines (> {large_file_lines}); consider splitting"))

    if raw and not raw.endswith("\n"):
        findings.append(Finding(name, len(lines), "info", "no-final-newline",
                                 "file does not end with a newline"))

    blank_run = 0
    comment_run = 0
    for i, line in enumerate(lines, start=1):
        # merge conflicts first: these make a file un-mergeable
        if CONFLICT_RE.match(line):
            findings.append(Finding(name, i, "error", "merge-conflict",
                                     "unresolved merge-conflict marker"))

        if line != line.rstrip():
            findings.append(Finding(name, i, "warn", "trailing-whitespace",
                                     "trailing whitespace"))

        if len(line) > max_line_length:
            findings.append(Finding(name, i, "info", "long-line",
                                     f"line is {len(line)} chars (> {max_line_length})"))

        for pattern, label in DEBUG_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(name, i, "warn", "debug-statement",
                                         f"possible debug leftover: {label}"))
                break

        if TODO_RE.search(line):
            marker = TODO_RE.search(line).group(1)
            findings.append(Finding(name, i, "info", "todo-marker",
                                     f"unresolved {marker} marker"))

        # consecutive blank lines (3+ in a row is dead space)
        if line.strip() == "":
            blank_run += 1
            if blank_run == 3:
                findings.append(Finding(name, i, "info", "excess-blank-lines",
                                         "3+ consecutive blank lines"))
        else:
            blank_run = 0

        # commented-out code: a run of comment lines that look like code
        m = COMMENT_PREFIX_RE.match(line)
        if m and CODE_SHAPE_RE.search(m.group(2) or ""):
            comment_run += 1
            if comment_run == 2:
                findings.append(Finding(name, i, "info", "commented-code",
                                         "looks like commented-out code (dead code / fluff)"))
        else:
            comment_run = 0

    return findings


def apply_safe_fixes(path: Path) -> FixResult | None:
    """Behavior-preserving only: trailing whitespace, blank-line runs, final newline."""
    result = FixResult(file=str(path))
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None

    lines = raw.splitlines()

    stripped = [ln.rstrip() for ln in lines]
    if stripped != lines:
        result.changes.append("removed trailing whitespace")

    collapsed: list[str] = []
    blank_run = 0
    for ln in stripped:
        if ln == "":
            blank_run += 1
            if blank_run <= 1:
                collapsed.append(ln)
        else:
            blank_run = 0
            collapsed.append(ln)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    if collapsed != stripped:
        result.changes.append("collapsed excess blank lines")

    new_text = "\n".join(collapsed) + ("\n" if collapsed else "")
    if new_text != raw:
        if not raw.endswith("\n") and collapsed:
            result.changes.append("added final newline")
        path.write_text(new_text, encoding="utf-8")
        return result
    return None


def render_report(findings: list[Finding]) -> str:
    if not findings:
        return "Clean: no hygiene findings."

    order = {"error": 0, "warn": 1, "info": 2}
    findings = sorted(findings, key=lambda f: (f.file, f.line, order.get(f.severity, 9)))

    lines = []
    current_file = None
    for f in findings:
        if f.file != current_file:
            current_file = f.file
            lines.append(f"\n{f.file}")
        lines.append(f"  {f.line:>5}  {f.severity:<5}  {f.code:<18}  {f.message}")

    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    summary = ", ".join(f"{counts[s]} {s}" for s in ("error", "warn", "info") if s in counts)
    lines.append(f"\nSummary: {summary} ({len(findings)} total)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Language-agnostic static code hygiene reviewer.")
    parser.add_argument("paths", nargs="+", help="files or directories to review")
    parser.add_argument("--max-line-length", type=int, default=120)
    parser.add_argument("--large-file-lines", type=int, default=600)
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    parser.add_argument("--fix", action="store_true",
                        help="apply safe, behavior-preserving cleanups in place")
    parser.add_argument("--fail-on", choices=["info", "warn", "error", "never"],
                        default="error", help="exit non-zero at this severity or above")
    args = parser.parse_args(argv)

    roots = [Path(p) for p in args.paths]
    for r in roots:
        if not r.exists():
            print(f"error: path not found: {r}", file=sys.stderr)
            return 2

    files = [p for p in iter_files(roots) if not is_probably_binary(p)]

    if args.fix:
        fixed = [r for p in files if (r := apply_safe_fixes(p))]
        if not fixed:
            print("Nothing to fix: files already clean.")
            return 0
        for r in fixed:
            print(f"{r.file}: {', '.join(r.changes)}")
        print(f"\nFixed {len(fixed)} file(s).")
        return 0

    findings: list[Finding] = []
    for p in files:
        findings.extend(analyze_file(p, args.max_line_length, args.large_file_lines))

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        print(render_report(findings))

    threshold = {"info": 0, "warn": 1, "error": 2, "never": 99}[args.fail_on]
    sev_rank = {"info": 0, "warn": 1, "error": 2}
    worst = max((sev_rank[f.severity] for f in findings), default=-1)
    return 1 if worst >= threshold else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # Output was piped into a command that closed early (e.g. `| head`).
        sys.exit(0)
