#!/usr/bin/env python3
"""Assemble the six-target public Beta Marketplace without publishing it."""

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
MARKETPLACE_NAME = "vivago"
CODEX_DISPLAY_NAME = "Vivago Agent CLI"
TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)
LEGAL_FILES = ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES.md")
BETA_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-beta\.([1-9]\d*)$"
)
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
PROD_LOGIN_ENDPOINT = b"https://vivago.ai/agent/login"
FORBIDDEN_MARKERS = (
    b"https://dev.vivago.ai",
    b"domestic-dev",
    b"domestic-prod",
    b"vivago-dev",
)
FORBIDDEN_MANIFEST_WORDING = re.compile(r"(?:\bdev\b|\bdevelopment\b|开发)", re.IGNORECASE)
CODEX_BRAND_FIELDS = (
    "name",
    "description",
    "interface.displayName",
    "interface.shortDescription",
    "interface.longDescription",
)
CLAUDE_BRAND_FIELDS = ("name", "description")


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


def _set_codex_manifest(path: Path, version: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    interface = payload.get("interface")
    if not isinstance(interface, dict):
        raise ValueError("Codex plugin manifest must contain an interface object")
    payload["version"] = version
    interface["displayName"] = CODEX_DISPLAY_NAME
    _write_json(path, payload)


def _field_value(payload: dict[str, Any], field: str) -> str:
    value: Any = payload
    for part in field.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"plugin manifest is missing branding field: {field}")
        value = value[part]
    if not isinstance(value, str):
        raise ValueError(f"plugin manifest branding field must be a string: {field}")
    return value


def _validate_beta_manifest_branding(
    codex_manifest: dict[str, Any], claude_manifest: dict[str, Any]
) -> None:
    for manifest_name, payload, fields in (
        ("Codex", codex_manifest, CODEX_BRAND_FIELDS),
        ("Claude", claude_manifest, CLAUDE_BRAND_FIELDS),
    ):
        for field in fields:
            if FORBIDDEN_MANIFEST_WORDING.search(_field_value(payload, field)):
                raise ValueError(
                    f"{manifest_name} plugin manifest contains development wording in {field}"
                )
    if _field_value(codex_manifest, "interface.displayName") != CODEX_DISPLAY_NAME:
        raise ValueError(f"Codex plugin displayName must be {CODEX_DISPLAY_NAME!r}")


def _validate_beta_skill_guidance(plugin: Path) -> None:
    skill_root = plugin / "skills" / PLUGIN_NAME
    metadata = skill_root / "agents" / "openai.yaml"
    expected_display_name = f'display_name: "{CODEX_DISPLAY_NAME}"'
    metadata_lines = {
        line.strip() for line in metadata.read_text(encoding="utf-8").splitlines()
    }
    if expected_display_name not in metadata_lines:
        raise ValueError(f"Skill display_name must be {CODEX_DISPLAY_NAME!r}")
    for path in skill_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml"}:
            if FORBIDDEN_MANIFEST_WORDING.search(path.read_text(encoding="utf-8")):
                raise ValueError(
                    "skill guidance contains development wording: "
                    f"{path.relative_to(plugin).as_posix()}"
                )


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
    if not BETA_VERSION.fullmatch(args.version):
        raise ValueError("beta version must match X.Y.Z-beta.N with N greater than zero")
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

    source_revision = args.source_revision.lower()
    binaries: dict[str, Path] = {}
    for target in TARGETS:
        binary = _target_binary(args.binary_root, target)
        if not binary.is_file():
            raise ValueError(f"missing target binary: {target}")
        binary_data = binary.read_bytes()
        if (
            args.version.encode() not in binary_data
            or source_revision.encode() not in binary_data
            or PROD_LOGIN_ENDPOINT not in binary_data
        ):
            raise ValueError(f"target binary provenance mismatch: {target}")
        if any(marker in binary_data for marker in FORBIDDEN_MARKERS):
            raise ValueError(f"target binary contains a forbidden endpoint: {target}")
        binaries[target] = binary
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")

    plugin = args.output / "plugins" / PLUGIN_NAME
    try:
        plugin.parent.mkdir(parents=True)
        shutil.copytree(
            args.plugin_template,
            plugin,
            ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc"),
        )
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
        (scripts / "vivago-agent.cmd").write_text(
            _windows_launcher(), encoding="utf-8", newline="\r\n"
        )

        codex_manifest_path = plugin / ".codex-plugin" / "plugin.json"
        claude_manifest_path = plugin / ".claude-plugin" / "plugin.json"
        _set_codex_manifest(codex_manifest_path, args.version)
        _set_manifest_version(claude_manifest_path, args.version)
        _validate_beta_manifest_branding(
            json.loads(codex_manifest_path.read_text(encoding="utf-8")),
            json.loads(claude_manifest_path.read_text(encoding="utf-8")),
        )
        _validate_beta_skill_guidance(plugin)
        (plugin / "VERSION").write_text(args.version + "\n", encoding="utf-8")
        _write_json(
            plugin / "BUILD_INFO.json",
            {
                "version": args.version,
                "source_revision": source_revision,
                "channel": "beta",
                "profile": "prod",
                "targets": list(TARGETS),
            },
        )

        for path in plugin.rglob("*"):
            if path.is_file() and any(marker in path.read_bytes() for marker in FORBIDDEN_MARKERS):
                raise ValueError(f"plugin template contains a forbidden environment marker: {path}")

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
                "interface": {"displayName": CODEX_DISPLAY_NAME},
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
                    "description": "Marketplace for the cross-platform VivagoAgent Go CLI."
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
    except Exception:
        shutil.rmtree(args.output, ignore_errors=True)
        raise
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
