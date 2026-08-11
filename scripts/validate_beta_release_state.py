#!/usr/bin/env python3
"""Fail-closed validation for creating or resuming a public Beta release."""

from __future__ import annotations

import argparse
import hashlib
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
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--checksums", type=Path, required=True)
    parser.add_argument("--tag-revision")
    parser.add_argument("--release-json", type=Path)
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(args: argparse.Namespace) -> str:
    if not BETA_VERSION.fullmatch(args.version):
        raise ValueError("beta version must match X.Y.Z-beta.N with N greater than zero")
    if not REVISION.fullmatch(args.source_revision):
        raise ValueError("source revision must be a full 40-character Git SHA")
    if args.tag_revision is not None and not REVISION.fullmatch(args.tag_revision):
        raise ValueError("tag revision must be a full 40-character Git SHA")

    release_exists = args.release_json is not None
    tag_exists = args.tag_revision is not None
    if not tag_exists and not release_exists:
        for path in (args.archive, args.sbom, args.checksums):
            if not path.is_file():
                raise ValueError(f"release input is missing: {path.name}")
        return "create_release"
    if tag_exists != release_exists:
        raise ValueError("existing tag requires an existing GitHub prerelease and vice versa")

    source_revision = args.source_revision.lower()
    if args.tag_revision.lower() != source_revision:
        raise ValueError("existing release tag revision does not match the requested source revision")

    release = json.loads(args.release_json.read_text(encoding="utf-8"))
    if not isinstance(release, dict):
        raise ValueError("release JSON must be an object")
    if release.get("tagName") != f"v{args.version}":
        raise ValueError("existing release tag name does not match the requested version")
    target = release.get("targetCommitish")
    if not isinstance(target, str) or target.lower() != source_revision:
        raise ValueError("existing release target does not match the requested source revision")
    if release.get("isPrerelease") is not True or release.get("isDraft") is not False:
        raise ValueError("existing release must be a published prerelease")

    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ValueError("existing release assets must be a list")
    digests: dict[str, str] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            raise ValueError("existing release asset must be an object")
        name = asset.get("name")
        digest = asset.get("digest")
        if isinstance(name, str) and isinstance(digest, str):
            if name in digests:
                raise ValueError(f"duplicate existing release asset: {name}")
            digests[name] = digest.lower()

    for path in (args.archive, args.sbom, args.checksums):
        if not path.is_file():
            raise ValueError(f"release input is missing: {path.name}")
        expected = f"sha256:{_sha256(path)}"
        if digests.get(path.name) != expected:
            raise ValueError(f"existing release asset digest does not match: {path.name}")
    return "resume_marketplace"


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
