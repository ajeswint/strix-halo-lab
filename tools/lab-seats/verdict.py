#!/usr/bin/env python3
"""Parse the adversarial-reviewer's first-line verdict.

Usage: verdict.py FILE      (or `-` / no argument for stdin)

Prints the verdict word on stdout. The first non-blank line must be exactly one of
APPROVE, APPROVE-WITH-NITS, REQUEST-CHANGES (surrounding whitespace allowed, nothing else:
a decorated or prefixed verdict is a format violation, not a verdict).
Exit codes: 0 APPROVE or APPROVE-WITH-NITS (nits do not block), 1 REQUEST-CHANGES,
2 missing or malformed (message on stderr).
"""
import sys

VERDICTS = ("APPROVE", "APPROVE-WITH-NITS", "REQUEST-CHANGES")


def parse(text):
    """Return the verdict if the first non-blank line is exactly one, else None."""
    for line in text.splitlines():
        stripped = line.strip().lstrip("﻿")
        if stripped:
            return stripped if stripped in VERDICTS else None
    return None


def main(argv):
    if len(argv) > 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = argv[1] if len(argv) == 2 else "-"
    try:
        text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    except OSError as e:
        print(f"verdict.py: {e}", file=sys.stderr)
        return 2
    v = parse(text)
    if v is None:
        print("verdict.py: first non-blank line is not APPROVE, APPROVE-WITH-NITS or REQUEST-CHANGES",
              file=sys.stderr)
        return 2
    print(v)
    return 1 if v == "REQUEST-CHANGES" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
