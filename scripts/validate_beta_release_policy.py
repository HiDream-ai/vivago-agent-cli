#!/usr/bin/env python3
"""Validate the fixed company-GitHub public Beta release boundary."""

from __future__ import annotations

import argparse
import json
import sys

from release_policy import validate_beta


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--source-revision", required=True)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    try:
        validate_beta(args.version, args.repository, args.ref, args.source_revision)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "channel": "beta"}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
