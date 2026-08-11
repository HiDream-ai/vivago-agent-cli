#!/usr/bin/env python3
"""Prevent a Beta retry from replacing Marketplace with older or conflicting output."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


BETA_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-beta\.([1-9]\d*)$"
)
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-version", required=True)
    parser.add_argument("--candidate-revision", required=True)
    parser.add_argument("--existing-build-info", type=Path)
    return parser.parse_args(argv)


def _version(value: str) -> tuple[int, int, int, int]:
    match = BETA_VERSION.fullmatch(value)
    if match is None:
        raise ValueError("Beta version must match X.Y.Z-beta.N with N greater than zero")
    return tuple(int(part) for part in match.groups())


def validate(args: argparse.Namespace) -> str:
    candidate = _version(args.candidate_version)
    if not REVISION.fullmatch(args.candidate_revision):
        raise ValueError("candidate revision must be a full 40-character Git SHA")
    if args.existing_build_info is None:
        return "initialize"

    existing = json.loads(args.existing_build_info.read_text(encoding="utf-8"))
    if not isinstance(existing, dict):
        raise ValueError("existing BUILD_INFO.json must be an object")
    if existing.get("channel") != "beta" or existing.get("profile") != "prod":
        raise ValueError("existing Marketplace is not a production Beta")
    existing_version_text = existing.get("version")
    existing_revision = existing.get("source_revision")
    if not isinstance(existing_version_text, str):
        raise ValueError("existing Marketplace version is missing")
    if not isinstance(existing_revision, str) or not REVISION.fullmatch(existing_revision):
        raise ValueError("existing Marketplace source revision is invalid")

    current = _version(existing_version_text)
    candidate_revision = args.candidate_revision.lower()
    existing_revision = existing_revision.lower()
    if current == candidate:
        if existing_revision != candidate_revision:
            raise ValueError("same Beta version already points to a different source revision")
        return "already_current"
    if current > candidate:
        raise ValueError("existing Marketplace contains a newer Beta and cannot be overwritten")
    return "update"


def main(argv: list[str] | None = None) -> int:
    try:
        action = validate(_arguments(argv))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "action": action}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
