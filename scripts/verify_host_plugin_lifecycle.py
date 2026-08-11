#!/usr/bin/env python3
"""Verify VivagoAgent plugin install, upgrade, rollback, and re-upgrade in one host."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple


TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)
HOSTS = ("codex", "claude-code")
CASES = tuple((target, host) for target in TARGETS for host in HOSTS)
PHASES = (
    ("install", "previous"),
    ("upgrade", "candidate"),
    ("rollback", "previous"),
    ("reupgrade", "candidate"),
)
PLUGIN_ID = "vivago-agent-cli@vivago-dev"
PLUGIN_NAME = "vivago-agent-cli"
MARKETPLACE_NAME = "vivago-dev"
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
DEV_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-dev\.([1-9]\d*)$"
)
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


class HostPolicy(NamedTuple):
    channel: str
    profile: str
    environment: str
    plugin_id: str
    marketplace_name: str
    version_pattern: re.Pattern[str]


DEV_POLICY = HostPolicy(
    channel="dev",
    profile="dev",
    environment="overseas-test",
    plugin_id=PLUGIN_ID,
    marketplace_name=MARKETPLACE_NAME,
    version_pattern=DEV_VERSION,
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--previous-marketplace", type=Path, required=True)
    parser.add_argument("--expected-target", choices=TARGETS, required=True)
    parser.add_argument("--host", choices=HOSTS, required=True)
    parser.add_argument("--host-version", required=True)
    parser.add_argument("--candidate-version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--report", type=Path, required=True)
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


def _host_environment(host: str, root: Path) -> dict[str, str]:
    if host == "codex":
        home = root / "codex-home"
        home.mkdir(parents=True, exist_ok=True)
        return {"CODEX_HOME": str(home)}
    if host == "claude-code":
        home = root / "claude-home"
        home.mkdir(parents=True, exist_ok=True)
        return {
            "CLAUDE_CONFIG_DIR": str(home),
            "DISABLE_AUTOUPDATER": "1",
        }
    raise ValueError(f"unsupported host: {host}")


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


def _replace_marketplace(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"Marketplace directory does not exist: {source}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".git"))


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return payload


def _build_info(
    marketplace: Path,
    policy: HostPolicy = DEV_POLICY,
) -> dict[str, Any]:
    plugin = marketplace / "plugins" / PLUGIN_NAME
    build_info = _read_json(plugin / "BUILD_INFO.json")
    expected_static = {
        "channel": policy.channel,
        "profile": policy.profile,
        "targets": list(TARGETS),
    }
    for key, value in expected_static.items():
        if build_info.get(key) != value:
            raise ValueError(f"Marketplace BUILD_INFO.json has invalid {key}")
    version = (plugin / "VERSION").read_text(encoding="utf-8").strip()
    if build_info.get("version") != version:
        raise ValueError("Marketplace VERSION and BUILD_INFO.json do not match")
    if not policy.version_pattern.fullmatch(version):
        raise ValueError("Marketplace BUILD_INFO.json has invalid version")
    revision = build_info.get("source_revision")
    if not isinstance(revision, str) or not REVISION.fullmatch(revision):
        raise ValueError("Marketplace source revision is not a full Git SHA")
    for relative in (
        Path(".agents/plugins/marketplace.json"),
        Path(".claude-plugin/marketplace.json"),
    ):
        manifest = marketplace / relative
        if not manifest.is_file():
            raise ValueError(f"Marketplace is missing {relative.as_posix()}")
        if _read_json(manifest).get("name") != policy.marketplace_name:
            raise ValueError(f"Marketplace has invalid name in {relative.as_posix()}")
    return build_info


def _host_executable(host: str) -> Path:
    command = "codex" if host == "codex" else "claude"
    executable = shutil.which(command)
    if executable is None:
        raise ValueError(f"{host} executable is not installed")
    return Path(executable)


def _host_command(executable: Path, target: str, arguments: list[str]) -> list[str]:
    if target.startswith("windows-") and executable.suffix.lower() in {".bat", ".cmd"}:
        return ["cmd.exe", "/d", "/c", "call", str(executable), *arguments]
    return [str(executable), *arguments]


def _launcher_command(launcher: Path, target: str, command: str) -> list[str]:
    if target.startswith("windows-"):
        return ["cmd.exe", "/d", "/c", "call", str(launcher), "--json", command]
    return [str(launcher), "--json", command]


def _check_sensitive_output(stdout: str, stderr: str, label: str) -> None:
    combined = f"{stdout}\n{stderr}".lower()
    if any(marker in combined for marker in SENSITIVE_MARKERS):
        raise ValueError(f"{label} output contains a sensitive field name")


def _run(
    command: list[str],
    *,
    environment: dict[str, str],
    cwd: Path,
    label: str,
    allowed_exits: tuple[int, ...] = (0,),
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env={**os.environ, **environment},
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    _check_sensitive_output(result.stdout, result.stderr, label)
    if result.returncode not in allowed_exits:
        raise ValueError(f"{label} failed with exit {result.returncode}")
    return result


def _json_stdout(result: subprocess.CompletedProcess[str], label: str) -> Any:
    stdout = result.stdout.strip()
    if not stdout:
        raise ValueError(f"{label} produced no JSON stdout")
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} stdout is not one JSON document") from exc


def _host_version(host: str, stdout: str) -> str:
    pattern = r"codex-cli\s+(\S+)" if host == "codex" else r"^(\S+)\s+\(Claude Code\)"
    match = re.search(pattern, stdout.strip())
    if match is None:
        raise ValueError(f"unable to parse {host} version")
    return match.group(1)


def _add_and_install(
    host: str,
    executable: Path,
    target: str,
    environment: dict[str, str],
    cwd: Path,
    marketplace: Path,
    policy: HostPolicy = DEV_POLICY,
) -> None:
    if host == "codex":
        _run(
            _host_command(
                executable,
                target,
                ["plugin", "marketplace", "add", str(marketplace), "--json"],
            ),
            environment=environment,
            cwd=cwd,
            label="Codex marketplace add",
        )
        _run(
            _host_command(executable, target, ["plugin", "add", policy.plugin_id, "--json"]),
            environment=environment,
            cwd=cwd,
            label="Codex plugin install",
        )
        return
    _run(
        _host_command(
            executable,
            target,
            ["plugin", "marketplace", "add", str(marketplace), "--scope", "user"],
        ),
        environment=environment,
        cwd=cwd,
        label="Claude Code marketplace add",
    )
    _run(
        _host_command(
            executable,
            target,
            ["plugin", "install", policy.plugin_id, "--scope", "user"],
        ),
        environment=environment,
        cwd=cwd,
        label="Claude Code plugin install",
    )


def _refresh_plugin(
    host: str,
    executable: Path,
    target: str,
    environment: dict[str, str],
    cwd: Path,
    marketplace: Path,
    policy: HostPolicy = DEV_POLICY,
) -> None:
    if host == "codex":
        _run(
            _host_command(
                executable,
                target,
                ["plugin", "marketplace", "remove", policy.marketplace_name, "--json"],
            ),
            environment=environment,
            cwd=cwd,
            label="Codex marketplace remove",
        )
        _run(
            _host_command(
                executable,
                target,
                ["plugin", "marketplace", "add", str(marketplace), "--json"],
            ),
            environment=environment,
            cwd=cwd,
            label="Codex marketplace re-add",
        )
        _run(
            _host_command(executable, target, ["plugin", "add", policy.plugin_id, "--json"]),
            environment=environment,
            cwd=cwd,
            label="Codex plugin refresh",
        )
        return
    _run(
        _host_command(
            executable,
            target,
            ["plugin", "marketplace", "update", policy.marketplace_name],
        ),
        environment=environment,
        cwd=cwd,
        label="Claude Code marketplace update",
    )
    _run(
        _host_command(
            executable,
            target,
            ["plugin", "update", policy.plugin_id, "--scope", "user"],
        ),
        environment=environment,
        cwd=cwd,
        label="Claude Code plugin refresh",
    )


def _installed_record(
    host: str,
    executable: Path,
    target: str,
    environment: dict[str, str],
    cwd: Path,
    policy: HostPolicy = DEV_POLICY,
) -> dict[str, Any]:
    result = _run(
        _host_command(executable, target, ["plugin", "list", "--json"]),
        environment=environment,
        cwd=cwd,
        label=f"{host} plugin list",
    )
    payload = _json_stdout(result, f"{host} plugin list")
    records = payload.get("installed") if host == "codex" and isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError(f"{host} plugin list has an unexpected shape")
    identifier_key = "pluginId" if host == "codex" else "id"
    for record in records:
        if isinstance(record, dict) and record.get(identifier_key) == policy.plugin_id:
            return record
    raise ValueError(f"{host} did not report the installed VivagoAgent plugin")


def _parse_envelope(result: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    payload = _json_stdout(result, label)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} stdout must be a JSON object")
    return payload


def _verify_installed_plugin(
    *,
    host: str,
    executable: Path,
    target: str,
    environment: dict[str, str],
    cwd: Path,
    expected_version: str,
    expected_revision: str,
    isolated_root: Path,
    policy: HostPolicy = DEV_POLICY,
) -> dict[str, Any]:
    record = _installed_record(host, executable, target, environment, cwd, policy)
    if record.get("version") != expected_version:
        raise ValueError(f"{host} reported the wrong installed plugin version")
    if host == "codex":
        installed_path = (
            isolated_root
            / "plugins"
            / "cache"
            / policy.marketplace_name
            / PLUGIN_NAME
            / expected_version
        ).resolve()
    else:
        installed_path = Path(str(record.get("installPath", ""))).resolve()
    if not installed_path.is_relative_to(isolated_root.resolve()):
        raise ValueError(
            f"{host} installed the plugin outside its isolated configuration: "
            f"installed={installed_path}, isolated={isolated_root.resolve()}"
        )
    if (installed_path / "VERSION").read_text(encoding="utf-8").strip() != expected_version:
        raise ValueError("installed plugin VERSION does not match the lifecycle phase")

    launcher_name = "vivago-agent.cmd" if target.startswith("windows-") else "vivago-agent"
    launcher = installed_path / "skills" / PLUGIN_NAME / "scripts" / launcher_name
    if not launcher.is_file():
        raise ValueError(f"installed plugin is missing {launcher_name}")
    version_result = _run(
        _launcher_command(launcher, target, "version"),
        environment=environment,
        cwd=cwd,
        label="installed launcher version",
    )
    version_payload = _parse_envelope(version_result, "installed launcher version")
    version_data = version_payload.get("data")
    if (
        version_payload.get("ok") is not True
        or not isinstance(version_data, dict)
        or version_data.get("version") != expected_version
    ):
        raise ValueError("installed launcher reported the wrong version")

    doctor_result = _run(
        _launcher_command(launcher, target, "doctor"),
        environment=environment,
        cwd=cwd,
        label="installed launcher doctor",
        allowed_exits=(0, DEPENDENCY_EXIT),
    )
    doctor_payload = _parse_envelope(doctor_result, "installed launcher doctor")
    doctor_data = doctor_payload.get("data")
    checks = doctor_data.get("checks") if isinstance(doctor_data, dict) else None
    if not isinstance(checks, dict):
        raise ValueError("installed launcher doctor is missing checks")
    build = checks.get("build")
    platform_check = checks.get("platform")
    environment_check = checks.get("environment")
    if build != {
        "ok": True,
        "version": expected_version,
        "git_sha": expected_revision.lower(),
        "channel": policy.channel,
    }:
        raise ValueError("installed launcher build provenance is wrong")
    expected_os, expected_arch = target.split("-", 1)
    if platform_check != {"ok": True, "os": expected_os, "arch": expected_arch}:
        raise ValueError("installed launcher selected the wrong platform binary")
    if environment_check != {
        "ok": True,
        "profile": policy.profile,
        "target": policy.environment,
    }:
        raise ValueError(
            f"installed launcher is not using the expected {policy.environment} profile"
        )
    return {
        "version": expected_version,
        "launcher": launcher_name,
        "doctor_exit": doctor_result.returncode,
    }


def verify(
    args: argparse.Namespace,
    policy: HostPolicy = DEV_POLICY,
) -> dict[str, Any]:
    if not REVISION.fullmatch(args.source_revision):
        raise ValueError("source revision must be a full 40-character Git SHA")
    detected_target = detect_native_target()
    if detected_target != args.expected_target:
        raise ValueError(
            f"runner target mismatch: expected {args.expected_target}, detected {detected_target}"
        )

    with tempfile.TemporaryDirectory(prefix="vivago-host-lifecycle-") as directory:
        scratch = Path(directory)
        candidate = scratch / "candidate"
        candidate.mkdir()
        _safe_extract(args.archive, candidate)
        previous_info = _build_info(args.previous_marketplace, policy)
        candidate_info = _build_info(candidate, policy)
        previous_version = str(previous_info["version"])
        candidate_version = str(candidate_info["version"])
        if candidate_version != args.candidate_version:
            raise ValueError("candidate Marketplace version does not match the release request")
        if candidate_info.get("source_revision", "").lower() != args.source_revision.lower():
            raise ValueError("candidate Marketplace source revision does not match the release request")
        if previous_version == candidate_version:
            raise ValueError("previous and candidate Marketplace versions must differ")

        work = scratch / "work"
        work.mkdir()
        marketplace = scratch / "marketplace"
        _replace_marketplace(args.previous_marketplace, marketplace)
        environment = _host_environment(args.host, scratch)
        isolated_root = Path(
            environment["CODEX_HOME"]
            if args.host == "codex"
            else environment["CLAUDE_CONFIG_DIR"]
        )
        executable = _host_executable(args.host)
        host_version_result = _run(
            _host_command(executable, detected_target, ["--version"]),
            environment=environment,
            cwd=work,
            label=f"{args.host} version",
        )
        actual_host_version = _host_version(args.host, host_version_result.stdout)
        if actual_host_version != args.host_version:
            raise ValueError(
                f"{args.host} version mismatch: expected {args.host_version}, got {actual_host_version}"
            )

        phase_reports: list[dict[str, Any]] = []
        for index, (phase, source_name) in enumerate(PHASES):
            source = args.previous_marketplace if source_name == "previous" else candidate
            build_info = previous_info if source_name == "previous" else candidate_info
            if index == 0:
                _add_and_install(
                    args.host,
                    executable,
                    detected_target,
                    environment,
                    work,
                    marketplace,
                    policy,
                )
            else:
                _replace_marketplace(source, marketplace)
                _refresh_plugin(
                    args.host,
                    executable,
                    detected_target,
                    environment,
                    work,
                    marketplace,
                    policy,
                )
            verified = _verify_installed_plugin(
                host=args.host,
                executable=executable,
                target=detected_target,
                environment=environment,
                cwd=work,
                expected_version=str(build_info["version"]),
                expected_revision=str(build_info["source_revision"]),
                isolated_root=isolated_root,
                policy=policy,
            )
            phase_reports.append({"phase": phase, **verified})

    report: dict[str, Any] = {
        "ok": True,
        "target": detected_target,
        "host": args.host,
        "host_version": actual_host_version,
        "previous_version": previous_version,
        "candidate_version": candidate_version,
        "source_revision": args.source_revision.lower(),
        "channel": policy.channel,
        "profile": policy.profile,
        "environment": policy.environment,
        "phases": phase_reports,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _write_failure_report(args: argparse.Namespace, message: str) -> None:
    report = {
        "ok": False,
        "target": args.expected_target,
        "host": args.host,
        "candidate_version": args.candidate_version,
        "source_revision": args.source_revision.lower(),
        "failure": message,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main_for_policy(
    argv: list[str] | None,
    policy: HostPolicy,
) -> int:
    args = _arguments(argv)
    try:
        report = verify(args, policy)
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
        tarfile.TarError,
    ) as exc:
        message = str(exc)
        _write_failure_report(args, message)
        print(f"error: {message}", file=sys.stderr)
        return 1
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    return main_for_policy(argv, DEV_POLICY)


if __name__ == "__main__":
    raise SystemExit(main())
