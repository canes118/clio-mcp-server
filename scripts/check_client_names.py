#!/usr/bin/env python3
"""Block commits that contain client names on a local denylist.

The denylist lives at `.client-names` (gitignored). Each non-blank,
non-comment line is a term matched case-insensitively as a whole word
against the content of every staged file passed on the command line.

Defense-in-depth only: the confidentiality principle in CLAUDE.md still
governs anything the hook does not catch (partial matches, paraphrases,
non-name identifiers, new names not yet added to the denylist).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DENYLIST_PATH = REPO_ROOT / ".client-names"
SCRIPT_PATH = Path(__file__).resolve()


def load_denylist(path: Path) -> list[str]:
    terms: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line)
    return terms


def compile_patterns(terms: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    return [
        (term, re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE))
        for term in terms
    ]


def scan_file(
    path: Path, patterns: list[tuple[str, re.Pattern[str]]]
) -> list[tuple[str, int]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    hits: list[tuple[str, int]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for term, pattern in patterns:
            if pattern.search(line):
                hits.append((term, lineno))
    return hits


def main(argv: list[str]) -> int:
    if not DENYLIST_PATH.exists():
        print(
            "WARNING: .client-names not found; client-name check skipped. "
            "Create it to enable enforcement.",
            file=sys.stderr,
        )
        return 0

    terms = load_denylist(DENYLIST_PATH)
    if not terms:
        return 0

    patterns = compile_patterns(terms)
    total_hits = 0

    for arg in argv:
        file_path = Path(arg)
        if not file_path.is_file():
            continue

        resolved = file_path.resolve()
        if resolved == DENYLIST_PATH.resolve() or resolved == SCRIPT_PATH:
            continue

        for term, lineno in scan_file(file_path, patterns):
            print(
                f"BLOCKED: {file_path} contains client name "
                f"'{term}' on line {lineno}",
                file=sys.stderr,
            )
            total_hits += 1

    if total_hits:
        print(
            f"Commit blocked: {total_hits} client-name match(es) found. "
            "Remove the matches or use `git commit --no-verify` to bypass "
            "(not recommended for this repo).",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
