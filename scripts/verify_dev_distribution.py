#!/usr/bin/env python3
"""Independently verify an assembled Vivago development Marketplace."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath


PLUGIN_NAME = "vivago-agent-cli"
TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
REQUIRED_ENDPOINT = b"https://dev.vivago.ai/agent/login"
FORBIDDEN_MARKERS = (
    b"https://vivago.ai/agent/login",
    b"domestic-dev",
    b"domestic-prod",
    b"storage-cdn.hidreamai.com",
    b"media.hidreamai.com",
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-revision", required=True)
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return payload


def _verify_checksums(plugin: Path) -> None:
    checksum_file = plugin / "SHA256SUMS"
    listed: set[str] = set()
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        digest, separator, relative_text = line.partition("  ")
        if separator != "  " or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid SHA256SUMS entry")
        relative = PurePosixPath(relative_text)
        if relative.is_absolute() or ".." in relative.parts or relative_text in listed:
            raise ValueError("unsafe or duplicate SHA256SUMS path")
        target = plugin.joinpath(*relative.parts)
        if not target.is_file() or _sha256(target) != digest:
            raise ValueError(f"checksum mismatch: {relative_text}")
        listed.add(relative_text)

    expected = {
        path.relative_to(plugin).as_posix()
        for path in plugin.rglob("*")
        if path.is_file() and path != checksum_file
    }
    if listed != expected:
        raise ValueError("SHA256SUMS does not cover the complete plugin")


def verify(args: argparse.Namespace) -> Path:
    if not SEMVER.fullmatch(args.version) or "-dev." not in args.version:
        raise ValueError("development version must be valid SemVer containing -dev.")
    if not REVISION.fullmatch(args.source_revision):
        raise ValueError("source revision must be a full 40-character Git SHA")

    marketplace = args.marketplace.resolve()
    plugin = marketplace / "plugins" / PLUGIN_NAME
    if not plugin.is_dir():
        raise ValueError("Marketplace is missing the VivagoAgent plugin")

    build_info = _json(plugin / "BUILD_INFO.json")
    expected_info = {
        "version": args.version,
        "source_revision": args.source_revision.lower(),
        "channel": "dev",
        "profile": "dev",
        "targets": list(TARGETS),
    }
    if build_info != expected_info:
        raise ValueError("BUILD_INFO.json does not match the requested development build")
    if (plugin / "VERSION").read_text(encoding="utf-8").strip() != args.version:
        raise ValueError("VERSION does not match the requested development build")

    for manifest in (
        plugin / ".codex-plugin" / "plugin.json",
        plugin / ".claude-plugin" / "plugin.json",
    ):
        if _json(manifest).get("version") != args.version:
            raise ValueError(f"plugin manifest version mismatch: {manifest}")
    if _json(marketplace / ".agents" / "plugins" / "marketplace.json").get("name") != "vivago-dev":
        raise ValueError("Codex Marketplace must be named vivago-dev")
    if _json(marketplace / ".claude-plugin" / "marketplace.json").get("name") != "vivago-dev":
        raise ValueError("Claude Marketplace must be named vivago-dev")

    for target in TARGETS:
        name = "vivago-agent.exe" if target.startswith("windows-") else "vivago-agent"
        binary = plugin / "bin" / target / name
        data = binary.read_bytes()
        if (
            args.version.encode() not in data
            or args.source_revision.lower().encode() not in data
            or REQUIRED_ENDPOINT not in data
        ):
            raise ValueError(f"binary provenance mismatch: {target}")

    for path in marketplace.rglob("*"):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if any(marker in data for marker in FORBIDDEN_MARKERS):
            raise ValueError(f"forbidden environment marker: {path.relative_to(marketplace)}")

    _verify_checksums(plugin)
    return plugin


def main(argv: list[str] | None = None) -> int:
    try:
        plugin = verify(_arguments(argv))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "plugin": str(plugin)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
