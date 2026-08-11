#!/usr/bin/env python3
"""Validate the fixed personal-GitHub development release boundary."""

from __future__ import annotations

import argparse
import json
import sys

from release_policy import validate_dev


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
        validate_dev(args.version, args.repository, args.ref, args.source_revision)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "channel": "dev"}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
