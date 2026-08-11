#!/usr/bin/env python3
"""Assemble the six-target Go development marketplace without publishing it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


PLUGIN_NAME = "vivago-agent-cli"
MARKETPLACE_NAME = "vivago-dev"
TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)
LEGAL_FILES = ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES.md")
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
DEV_LOGIN_ENDPOINT = b"https://dev.vivago.ai/agent/login"
FORBIDDEN_ENDPOINTS = (
    b"https://vivago.ai/agent/login",
    b"domestic-dev",
    b"domestic-prod",
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-template", type=Path, required=True)
    parser.add_argument("--binary-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-revision", required=True)
    return parser.parse_args(argv)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _set_manifest_version(path: Path, version: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = version
    _write_json(path, payload)


def _target_binary(binary_root: Path, target: str) -> Path:
    name = "vivago-agent.exe" if target.startswith("windows-") else "vivago-agent"
    return binary_root / target / name


def _posix_launcher() -> str:
    return """#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OS_NAME=$(uname -s)
ARCH_NAME=$(uname -m)
case "$OS_NAME" in
  Darwin) TARGET_OS=darwin ;;
  Linux) TARGET_OS=linux ;;
  MINGW*|MSYS*|CYGWIN*) TARGET_OS=windows ;;
  *)
    printf '%s\n' '{"ok":false,"data":null,"error":{"code":"UNSUPPORTED_PLATFORM","message":"No bundled VivagoAgent binary matches this operating system."}}'
    exit 40
    ;;
esac
case "$ARCH_NAME" in
  arm64|aarch64) TARGET_ARCH=arm64 ;;
  x86_64|amd64) TARGET_ARCH=amd64 ;;
  *)
    printf '%s\n' '{"ok":false,"data":null,"error":{"code":"UNSUPPORTED_PLATFORM","message":"No bundled VivagoAgent binary matches this CPU architecture."}}'
    exit 40
    ;;
esac
BINARY="$SCRIPT_DIR/../../../bin/$TARGET_OS-$TARGET_ARCH/vivago-agent"
if [ "$TARGET_OS" = windows ]; then
  BINARY="$BINARY.exe"
fi
if [ ! -x "$BINARY" ]; then
  printf '%s\n' '{"ok":false,"data":null,"error":{"code":"PLUGIN_RUNTIME_MISSING","message":"The bundled VivagoAgent binary is missing; reinstall the plugin."}}'
  exit 40
fi
exec "$BINARY" "$@"
"""


def _windows_launcher() -> str:
    return r"""@echo off
setlocal
set "ARCH=%PROCESSOR_ARCHITECTURE%"
if /I "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "ARCH=ARM64"
if /I "%PROCESSOR_ARCHITEW6432%"=="AMD64" set "ARCH=AMD64"
if /I "%ARCH%"=="ARM64" set "TARGET=windows-arm64"
if /I "%ARCH%"=="AMD64" set "TARGET=windows-amd64"
if not defined TARGET (
  echo {"ok":false,"data":null,"error":{"code":"UNSUPPORTED_PLATFORM","message":"No bundled VivagoAgent binary matches this CPU architecture."}}
  exit /b 40
)
set "BINARY=%~dp0..\..\..\bin\%TARGET%\vivago-agent.exe"
if not exist "%BINARY%" (
  echo {"ok":false,"data":null,"error":{"code":"PLUGIN_RUNTIME_MISSING","message":"The bundled VivagoAgent binary is missing; reinstall the plugin."}}
  exit /b 40
)
"%BINARY%" %*
exit /b %ERRORLEVEL%
"""


def assemble(args: argparse.Namespace) -> Path:
    if not SEMVER.fullmatch(args.version) or "-dev." not in args.version:
        raise ValueError("development version must be valid SemVer containing -dev.")
    if not REVISION.fullmatch(args.source_revision):
        raise ValueError("source revision must be a full 40-character Git SHA")
    if not args.plugin_template.is_dir():
        raise ValueError(f"plugin template does not exist: {args.plugin_template}")
    for relative in (
        Path(".codex-plugin/plugin.json"),
        Path(".claude-plugin/plugin.json"),
        Path("skills/vivago-agent-cli/SKILL.md"),
    ):
        if not (args.plugin_template / relative).is_file():
            raise ValueError(f"plugin template is missing {relative.as_posix()}")
    legal_root = args.plugin_template.resolve().parent
    for name in LEGAL_FILES:
        if not (legal_root / name).is_file():
            raise ValueError(f"repository is missing required legal file: {name}")
    binaries: dict[str, Path] = {}
    for target in TARGETS:
        binary = _target_binary(args.binary_root, target)
        if not binary.is_file():
            raise ValueError(f"missing target binary: {target}")
        binary_data = binary.read_bytes()
        if (
            args.version.encode() not in binary_data
            or args.source_revision.lower().encode() not in binary_data
            or DEV_LOGIN_ENDPOINT not in binary_data
        ):
            raise ValueError(f"target binary provenance mismatch: {target}")
        if any(marker in binary_data for marker in FORBIDDEN_ENDPOINTS):
            raise ValueError(f"target binary contains a forbidden endpoint: {target}")
        binaries[target] = binary
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")

    plugin = args.output / "plugins" / PLUGIN_NAME
    plugin.parent.mkdir(parents=True)
    shutil.copytree(args.plugin_template, plugin)
    for name in LEGAL_FILES:
        shutil.copy2(legal_root / name, plugin / name)
    for target, source in binaries.items():
        destination = plugin / "bin" / target / source.name
        destination.parent.mkdir(parents=True)
        shutil.copy2(source, destination)
        destination.chmod(0o755)

    scripts = plugin / "skills" / PLUGIN_NAME / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    posix_launcher = scripts / "vivago-agent"
    posix_launcher.write_text(_posix_launcher(), encoding="utf-8")
    posix_launcher.chmod(0o755)
    windows_launcher = scripts / "vivago-agent.cmd"
    windows_launcher.write_text(_windows_launcher(), encoding="utf-8", newline="\r\n")

    _set_manifest_version(plugin / ".codex-plugin" / "plugin.json", args.version)
    _set_manifest_version(plugin / ".claude-plugin" / "plugin.json", args.version)
    (plugin / "VERSION").write_text(args.version + "\n", encoding="utf-8")
    _write_json(
        plugin / "BUILD_INFO.json",
        {
            "version": args.version,
            "source_revision": args.source_revision.lower(),
            "channel": "dev",
            "profile": "dev",
            "targets": list(TARGETS),
        },
    )

    checksum_targets = sorted(
        (path for path in plugin.rglob("*") if path.is_file()),
        key=lambda path: path.as_posix(),
    )
    checksum_lines = [
        f"{_sha256(path)}  {path.relative_to(plugin).as_posix()}" for path in checksum_targets
    ]
    (plugin / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    _write_json(
        args.output / ".agents" / "plugins" / "marketplace.json",
        {
            "name": MARKETPLACE_NAME,
            "interface": {"displayName": "Vivago Dev"},
            "plugins": [
                {
                    "name": PLUGIN_NAME,
                    "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
                    "category": "Productivity",
                }
            ],
        },
    )
    _write_json(
        args.output / ".claude-plugin" / "marketplace.json",
        {
            "name": MARKETPLACE_NAME,
            "owner": {"name": "HiDream"},
            "metadata": {
                "description": "Development marketplace for the cross-platform VivagoAgent Go CLI."
            },
            "plugins": [
                {
                    "name": PLUGIN_NAME,
                    "source": f"./plugins/{PLUGIN_NAME}",
                    "description": "Delegate creative tasks through the bundled VivagoAgent Go CLI.",
                    "version": args.version,
                }
            ],
        },
    )
    return plugin


def main(argv: list[str] | None = None) -> int:
    try:
        plugin = assemble(_arguments(argv))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "plugin": str(plugin)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
