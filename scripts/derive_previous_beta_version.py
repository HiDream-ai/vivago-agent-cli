#!/usr/bin/env python3
"""Derive a strictly lower synthetic Beta used only for lifecycle validation."""

from __future__ import annotations

import argparse
import re
import sys


BETA_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-beta\.([1-9]\d*)$"
)
SYNTHETIC_MAX = 999_999


def derive(version: str) -> str:
    match = BETA_VERSION.fullmatch(version)
    if match is None:
        raise ValueError("beta version must match X.Y.Z-beta.N with N greater than zero")
    major, minor, patch, sequence = (int(value) for value in match.groups())
    if sequence > 1:
        return f"{major}.{minor}.{patch}-beta.{sequence - 1}"
    if patch > 0:
        return f"{major}.{minor}.{patch - 1}-beta.{SYNTHETIC_MAX}"
    if minor > 0:
        return f"{major}.{minor - 1}.{SYNTHETIC_MAX}-beta.{SYNTHETIC_MAX}"
    if major > 0:
        return f"{major - 1}.{SYNTHETIC_MAX}.{SYNTHETIC_MAX}-beta.{SYNTHETIC_MAX}"
    raise ValueError("no lower synthetic Beta version exists for 0.0.0-beta.1")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    try:
        previous = derive(args.version)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(previous)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
