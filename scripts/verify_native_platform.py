#!/usr/bin/env python3
"""Verify one assembled VivagoAgent plugin on its native GitHub runner."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
MAX_ARCHIVE_MEMBERS = 5_000
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
DEPENDENCY_EXIT = 40
SENSITIVE_MARKERS = (
    "access_token",
    "authorization",
    "cookie",
    "presigned_url",
    "refresh_token",
    "ticket",
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--expected-target", choices=TARGETS, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--report", type=Path)
    return parser.parse_args(argv)


def detect_native_target() -> str:
    system = platform.system().strip().lower()
    machine = platform.machine().strip().lower()
    try:
        operating_system = {
            "darwin": "darwin",
            "linux": "linux",
            "windows": "windows",
        }[system]
        architecture = {
            "arm64": "arm64",
            "aarch64": "arm64",
            "amd64": "amd64",
            "x86_64": "amd64",
        }[machine]
    except KeyError as exc:
        raise ValueError(f"unsupported native runner: {system}-{machine}") from exc
    target = f"{operating_system}-{architecture}"
    if target not in TARGETS:
        raise ValueError(f"unsupported native runner: {target}")
    return target


def _safe_extract(archive: Path, destination: Path) -> None:
    if not archive.is_file():
        raise ValueError(f"Marketplace archive does not exist: {archive}")
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ValueError("Marketplace archive contains too many entries")
        total_size = 0
        for member in members:
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Marketplace archive contains an unsafe path")
            if member.issym() or member.islnk() or member.isdev():
                raise ValueError("Marketplace archive contains an unsupported entry type")
            if not (member.isdir() or member.isfile()):
                raise ValueError("Marketplace archive contains an unsupported entry type")
            total_size += member.size
            if total_size > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("Marketplace archive is too large after extraction")
        bundle.extractall(destination)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return payload


def _launcher_command(launcher: Path, command: str, target: str) -> list[str]:
    if target.startswith("windows-"):
        return ["cmd.exe", "/d", "/c", "call", str(launcher), "--json", command]
    return [str(launcher), "--json", command]


def _run_launcher(launcher: Path, command: str, target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _launcher_command(launcher, command, target),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _parse_envelope(result: subprocess.CompletedProcess[str], command: str) -> dict[str, Any]:
    stdout = result.stdout.strip()
    combined = (result.stdout + "\n" + result.stderr).lower()
    if any(marker in combined for marker in SENSITIVE_MARKERS):
        raise ValueError(f"{command} output contains a sensitive field name")
    if not stdout:
        raise ValueError(f"{command} produced no machine-readable stdout")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{command} stdout is not one JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{command} stdout must be a JSON object")
    return payload


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"missing {label} in doctor output")
    return value


def verify(
    args: argparse.Namespace,
    *,
    expected_channel: str = "dev",
    expected_profile: str = "dev",
    expected_environment: str = "overseas-test",
    expected_version: re.Pattern[str] | None = None,
    version_error: str = "version does not match the native smoke policy",
    environment_error: str = "doctor environment is not the overseas dev profile",
) -> dict[str, Any]:
    if expected_version is not None and not expected_version.fullmatch(args.version):
        raise ValueError(version_error)
    if not REVISION.fullmatch(args.source_revision):
        raise ValueError("source revision must be a full 40-character Git SHA")
    detected_target = detect_native_target()
    if detected_target != args.expected_target:
        raise ValueError(
            f"runner target mismatch: expected {args.expected_target}, detected {detected_target}"
        )

    with tempfile.TemporaryDirectory(prefix="vivago-native-smoke-") as directory:
        marketplace = Path(directory) / "marketplace"
        marketplace.mkdir()
        _safe_extract(args.archive, marketplace)
        plugin = marketplace / "plugins" / "vivago-agent-cli"
        build_info = _read_json(plugin / "BUILD_INFO.json")
        expected_build_info = {
            "version": args.version,
            "source_revision": args.source_revision.lower(),
            "channel": expected_channel,
            "profile": expected_profile,
            "targets": list(TARGETS),
        }
        if build_info != expected_build_info:
            raise ValueError("BUILD_INFO.json does not match the native smoke request")

        launcher_name = "vivago-agent.cmd" if detected_target.startswith("windows-") else "vivago-agent"
        launcher = plugin / "skills" / "vivago-agent-cli" / "scripts" / launcher_name
        if not launcher.is_file():
            raise ValueError(f"plugin launcher is missing: {launcher_name}")

        version_result = _run_launcher(launcher, "version", detected_target)
        version_payload = _parse_envelope(version_result, "version")
        version_data = _mapping(version_payload.get("data"), "version data")
        if version_result.returncode != 0 or version_payload.get("ok") is not True:
            raise ValueError("native launcher version command failed")
        if version_data.get("version") != args.version:
            raise ValueError("native launcher reported the wrong version")

        doctor_result = _run_launcher(launcher, "doctor", detected_target)
        doctor_payload = _parse_envelope(doctor_result, "doctor")
        if doctor_result.returncode not in (0, DEPENDENCY_EXIT):
            raise ValueError(f"native launcher doctor returned exit {doctor_result.returncode}")
        doctor_data = _mapping(doctor_payload.get("data"), "doctor data")
        checks = _mapping(doctor_data.get("checks"), "doctor checks")
        build = _mapping(checks.get("build"), "doctor build check")
        platform_check = _mapping(checks.get("platform"), "doctor platform check")
        environment = _mapping(checks.get("environment"), "doctor environment check")
        credentials = _mapping(checks.get("credentials"), "doctor credential check")

        expected_os, expected_arch = detected_target.split("-", 1)
        actual_target = f"{platform_check.get('os')}-{platform_check.get('arch')}"
        if actual_target != detected_target or platform_check.get("ok") is not True:
            raise ValueError(
                f"launcher selected the wrong binary: expected {detected_target}, got {actual_target}"
            )
        if build != {
            "ok": True,
            "version": args.version,
            "git_sha": args.source_revision.lower(),
            "channel": expected_channel,
        }:
            raise ValueError("doctor build provenance does not match the requested artifact")
        if environment != {
            "ok": True,
            "profile": expected_profile,
            "target": expected_environment,
        }:
            raise ValueError(environment_error)

        allowed_backends = {
            "darwin": {"keychain"},
            "linux": {"file", "secret-service"},
            "windows": {"credential-manager"},
        }[expected_os]
        if credentials.get("backend") not in allowed_backends:
            raise ValueError("doctor reported an unexpected credential backend")
        if expected_arch not in {"arm64", "amd64"}:
            raise ValueError("doctor reported an unsupported architecture")

    report: dict[str, Any] = {
        "ok": True,
        "target": detected_target,
        "version": args.version,
        "source_revision": args.source_revision.lower(),
        "channel": expected_channel,
        "profile": expected_profile,
        "environment": expected_environment,
        "launcher": launcher_name,
        "doctor_exit": doctor_result.returncode,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def main_for_policy(
    argv: list[str] | None = None,
    *,
    expected_channel: str,
    expected_profile: str,
    expected_environment: str,
    expected_version: re.Pattern[str] | None = None,
    version_error: str = "version does not match the native smoke policy",
    environment_error: str,
) -> int:
    try:
        report = verify(
            _arguments(argv),
            expected_channel=expected_channel,
            expected_profile=expected_profile,
            expected_environment=expected_environment,
            expected_version=expected_version,
            version_error=version_error,
            environment_error=environment_error,
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
        tarfile.TarError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    return main_for_policy(
        argv,
        expected_channel="dev",
        expected_profile="dev",
        expected_environment="overseas-test",
        environment_error="doctor environment is not the overseas dev profile",
    )


if __name__ == "__main__":
    raise SystemExit(main())
