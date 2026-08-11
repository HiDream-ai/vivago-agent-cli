#!/usr/bin/env python3
"""Run ticket-only VivagoAgent L3 smoke checks through both installed plugin hosts."""

from __future__ import annotations

import argparse
import binascii
import json
import os
import platform
import queue
import re
import shutil
import subprocess
import struct
import sys
import threading
import time
import zlib
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit


TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)
HOSTS = ("codex", "claude-code")
PLUGIN_ID = "vivago-agent-cli@vivago-dev"
PLUGIN_NAME = "vivago-agent-cli"
MARKETPLACE_NAME = "vivago-dev"
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]+$")
IMAGE_ARTIFACT = re.compile(r"^[pj]_[0-9a-fA-F-]{20,}$")
SENSITIVE_MARKERS = (
    "access_token",
    "authorization",
    "cookie",
    "presigned_url",
    "refresh_token",
    "ticket",
)


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace", type=Path, required=True)
    parser.add_argument("--expected-target", choices=TARGETS, required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--run-id", required=True)
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
        raise ValueError("unsupported native runner") from exc
    target = f"{operating_system}-{architecture}"
    if target not in TARGETS:
        raise ValueError("unsupported native runner")
    return target


def launcher_command(launcher: Path, target: str, arguments: list[str]) -> list[str]:
    if target.startswith("windows-"):
        return ["cmd.exe", "/d", "/c", "call", str(launcher), *arguments]
    return [str(launcher), *arguments]


def host_command(executable: Path, target: str, arguments: list[str]) -> list[str]:
    if target.startswith("windows-") and executable.suffix.lower() in {".bat", ".cmd"}:
        return ["cmd.exe", "/d", "/c", "call", str(executable), *arguments]
    return [str(executable), *arguments]


def parse_finished_stream(stdout: str) -> dict[str, str]:
    return _parse_terminal_stream(stdout, "RUN_FINISHED", "expected terminal event")


def parse_cancelled_stream(stdout: str) -> dict[str, str]:
    return _parse_terminal_stream(stdout, "RUN_ERROR", "cancelled terminal event")


def _parse_finished_for(stdout: str, label: str) -> dict[str, str]:
    try:
        return parse_finished_stream(stdout)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def parse_resumed_stream(
    stdout: str,
    expected_conversation_id: str,
    expected_turn_id: str,
) -> dict[str, str]:
    if not SAFE_IDENTIFIER.fullmatch(expected_conversation_id):
        raise ValueError("resume expected an invalid conversation identifier")
    if not SAFE_IDENTIFIER.fullmatch(expected_turn_id):
        raise ValueError("resume expected an invalid turn identifier")
    records: list[dict[str, Any]] = []
    session_found = False
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("resumed stream stdout is not JSONL") from exc
        if not isinstance(record, dict):
            raise ValueError("resumed stream record must be an object")
        if record.get("type") == "session":
            session_found = True
            conversation_id = record.get("conversation_id")
            turn_id = record.get("turn_id")
            if conversation_id not in {"", expected_conversation_id}:
                raise ValueError("resume returned a different conversation")
            if turn_id != expected_turn_id:
                raise ValueError("resume returned a different turn")
            record = {**record, "conversation_id": expected_conversation_id}
        records.append(record)
    if not session_found:
        raise ValueError("resumed stream did not expose a session")
    normalized = "\n".join(json.dumps(record) for record in records)
    return parse_finished_stream(normalized)


def stream_text_matches(stdout: str, expected: str) -> bool:
    complete_messages: list[str] = []
    content_fragments: dict[str, list[str]] = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return False
        data = record.get("data") if isinstance(record, dict) else None
        if not isinstance(data, dict):
            continue
        message_type = data.get("type")
        if message_type == "TEXT_MESSAGE" and isinstance(data.get("text"), str):
            complete_messages.append(data["text"])
        if message_type == "TEXT_MESSAGE_CONTENT" and isinstance(data.get("delta"), str):
            message_id = data.get("messageId")
            if not isinstance(message_id, str) or not message_id:
                message_id = "unknown"
            content_fragments.setdefault(message_id, []).append(data["delta"])
    wanted = " ".join(expected.split()).casefold()
    candidates = complete_messages
    candidates.extend("".join(fragments) for fragments in content_fragments.values())
    return any(" ".join(candidate.split()).casefold() == wanted for candidate in candidates)


def write_attachment_fixture(path: Path) -> None:
    width = 96
    height = 32
    row = b"\xff\x00\x00" * 32 + b"\x00\xff\x00" * 32 + b"\x00\x00\xff" * 32
    raw = b"".join(b"\x00" + row for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = binascii.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, level=9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def extract_image_artifact(stdout: str) -> str:
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        data = record.get("data") if isinstance(record, dict) else None
        if not isinstance(data, dict) or data.get("type") != "TOOL_CALL_RESULT":
            continue
        content = data.get("content")
        if not isinstance(content, str):
            continue
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            continue
        if not isinstance(result, dict) or result.get("status") != "succeeded":
            continue
        if result.get("artifact_status") != "verified":
            continue
        artifacts = result.get("artifacts")
        images = artifacts.get("images") if isinstance(artifacts, dict) else None
        if not isinstance(images, list):
            continue
        for content_id in images:
            if isinstance(content_id, str) and IMAGE_ARTIFACT.fullmatch(content_id):
                return content_id
    raise ValueError("stream did not contain a verified image artifact")


def validate_artifact_file(data: Any, expected_path: Path | None = None) -> tuple[int, str, Path]:
    if not isinstance(data, dict):
        raise ValueError("artifact command returned an invalid result")
    raw_path = data.get("path")
    byte_count = data.get("bytes")
    content_type = data.get("content_type")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("artifact command returned an invalid path")
    path = Path(raw_path)
    if not path.is_absolute() or not path.is_file():
        raise ValueError("artifact command did not create an absolute local file")
    if expected_path is not None and path.resolve() != expected_path.resolve():
        raise ValueError("artifact command wrote to an unexpected path")
    if not isinstance(byte_count, int) or byte_count <= 0 or path.stat().st_size != byte_count:
        raise ValueError("artifact command returned an invalid byte count")
    if not isinstance(content_type, str) or not content_type.startswith("image/"):
        raise ValueError("artifact command returned an invalid image content type")
    return byte_count, content_type, path


def _parse_terminal_stream(
    stdout: str,
    expected_terminal: str,
    description: str,
) -> dict[str, str]:
    session: dict[str, Any] | None = None
    last_event_id = ""
    terminal_event = ""
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("stream stdout is not JSONL") from exc
        if not isinstance(record, dict):
            raise ValueError("stream record must be an object")
        if record.get("type") == "session":
            session = record
        event_id = record.get("event_id")
        if isinstance(event_id, str) and event_id:
            last_event_id = event_id
        data = record.get("data")
        event_type = data.get("type") if isinstance(data, dict) else None
        if event_type in {"RUN_FINISHED", "RUN_ERROR"}:
            terminal_event = str(event_type)
    if session is None or terminal_event != expected_terminal:
        raise ValueError(f"stream did not reach the {description}")
    conversation_id = session.get("conversation_id")
    turn_id = session.get("turn_id")
    for name, value in (
        ("conversation", conversation_id),
        ("turn", turn_id),
        ("event", last_event_id),
    ):
        if not isinstance(value, str) or not value or not SAFE_IDENTIFIER.fullmatch(value):
            raise ValueError(f"stream returned an invalid {name} identifier")
    return {
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "last_event_id": last_event_id,
        "terminal_event": terminal_event,
    }


def parse_stream_checkpoint(stdout: str) -> dict[str, str]:
    session: dict[str, Any] | None = None
    last_event_id = ""
    saw_nonterminal_event = False
    terminal_event = ""
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("stream stdout is not JSONL") from exc
        if not isinstance(record, dict):
            raise ValueError("stream record must be an object")
        if record.get("type") == "session":
            session = record
        event_id = record.get("event_id")
        data = record.get("data")
        event_type = data.get("type") if isinstance(data, dict) else None
        if event_type in {"RUN_FINISHED", "RUN_ERROR"}:
            terminal_event = str(event_type)
        elif isinstance(event_id, str) and event_id:
            last_event_id = event_id
            saw_nonterminal_event = True
    if terminal_event or not saw_nonterminal_event:
        raise ValueError("stream reached a terminal event before interruption")
    if session is None:
        raise ValueError("stream did not expose a session before interruption")
    conversation_id = session.get("conversation_id")
    turn_id = session.get("turn_id")
    for name, value in (
        ("conversation", conversation_id),
        ("turn", turn_id),
        ("event", last_event_id),
    ):
        if not isinstance(value, str) or not value or not SAFE_IDENTIFIER.fullmatch(value):
            raise ValueError(f"stream returned an invalid {name} identifier")
    return {
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "last_event_id": last_event_id,
    }


def validate_project_link(
    data: Any,
    project_id: str,
    conversation_id: str,
) -> str:
    if not isinstance(data, dict) or data.get("profile") != "dev":
        raise ValueError("project link did not report the development profile")
    if data.get("project_id") != project_id or data.get("conversation_id") != conversation_id:
        raise ValueError("project link changed the requested identifiers")
    deep_link = data.get("deep_link")
    if not isinstance(deep_link, str):
        raise ValueError("project link did not return a URL")
    parsed = urlsplit(deep_link)
    if parsed.scheme != "https" or parsed.netloc != "dev.vivago.ai":
        raise ValueError("project link returned an unexpected origin")
    if parsed.path != "/agent/new-chat" or parsed.fragment:
        raise ValueError("project link returned an unexpected path")
    if parse_qs(parsed.query, strict_parsing=True) != {
        "project_id": [project_id],
        "conversation_id": [conversation_id],
    }:
        raise ValueError("project link returned unexpected query parameters")
    return parsed.hostname or ""


def _run(
    command: list[str],
    *,
    environment: dict[str, str],
    cwd: Path,
    label: str,
    timeout: int = 180,
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
    combined = f"{result.stdout}\n{result.stderr}".lower()
    if any(marker in combined for marker in SENSITIVE_MARKERS):
        raise ValueError(f"{label} output contains a sensitive field")
    if result.returncode != 0:
        detail = safe_failure_detail(result.stdout)
        raise ValueError(f"{label} failed with exit {result.returncode}: {detail}")
    return result


def _terminate_process_tree(process: subprocess.Popen[str], target: str) -> None:
    if process.poll() is not None:
        return
    if target.startswith("windows-"):
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        return
    process.terminate()


def _interrupt_after_checkpoint(
    command: list[str],
    *,
    target: str,
    environment: dict[str, str],
    cwd: Path,
    label: str,
    timeout: int = 90,
) -> dict[str, str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env={**os.environ, **environment},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.stdout is None or process.stderr is None:
        _terminate_process_tree(process, target)
        raise ValueError(f"{label} did not expose process pipes")

    records: queue.Queue[str | None] = queue.Queue()

    def read_stdout() -> None:
        try:
            for line in process.stdout:
                records.put(line)
        finally:
            records.put(None)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    lines: list[str] = []
    checkpoint: dict[str, str] | None = None
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            try:
                line = records.get(timeout=min(1.0, max(0.1, deadline - time.monotonic())))
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if line is None:
                break
            lines.append(line)
            try:
                checkpoint = parse_stream_checkpoint("".join(lines))
            except ValueError:
                continue
            break
    finally:
        _terminate_process_tree(process, target)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        reader.join(timeout=5)

    stderr = process.stderr.read()
    combined = f"{''.join(lines)}\n{stderr}".lower()
    if any(marker in combined for marker in SENSITIVE_MARKERS):
        raise ValueError(f"{label} output contains a sensitive field")
    if checkpoint is None:
        raise ValueError(f"{label} did not expose a resumable checkpoint before termination")
    return checkpoint


def _cancel_active_stream(
    ask_command: list[str],
    cancel_command: Callable[[str, str], list[str]],
    *,
    target: str,
    environment: dict[str, str],
    cwd: Path,
    label: str,
    timeout: int = 300,
) -> dict[str, str]:
    process = subprocess.Popen(
        ask_command,
        cwd=cwd,
        env={**os.environ, **environment},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.stdout is None or process.stderr is None:
        _terminate_process_tree(process, target)
        raise ValueError(f"{label} did not expose process pipes")

    records: queue.Queue[str | None] = queue.Queue()
    all_lines: list[str] = []

    def read_stdout() -> None:
        try:
            for line in process.stdout:
                all_lines.append(line)
                records.put(line)
        finally:
            records.put(None)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    session: dict[str, str] | None = None
    run_started = False
    deadline = time.monotonic() + 90
    try:
        while time.monotonic() < deadline:
            try:
                line = records.get(timeout=min(1.0, max(0.1, deadline - time.monotonic())))
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if line is None:
                break
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{label} stdout is not JSONL") from exc
            if not isinstance(record, dict):
                continue
            if record.get("type") == "session":
                conversation_id = record.get("conversation_id")
                turn_id = record.get("turn_id")
                if not isinstance(conversation_id, str) or not SAFE_IDENTIFIER.fullmatch(conversation_id):
                    raise ValueError(f"{label} returned an invalid conversation identifier")
                if not isinstance(turn_id, str) or not SAFE_IDENTIFIER.fullmatch(turn_id):
                    raise ValueError(f"{label} returned an invalid turn identifier")
                session = {"conversation_id": conversation_id, "turn_id": turn_id}
                continue
            data = record.get("data")
            event_type = data.get("type") if isinstance(data, dict) else None
            if event_type == "RUN_STARTED" and session is not None:
                run_started = True
                break
            if event_type in {"RUN_FINISHED", "RUN_ERROR"}:
                break
        if session is None or not run_started:
            raise ValueError(f"{label} did not expose an active RUN_STARTED session")
        _envelope_data(
            _run(
                cancel_command(session["conversation_id"], session["turn_id"]),
                environment=environment,
                cwd=cwd,
                label=f"{label} cancel command",
            ),
            f"{label} cancel command",
        )
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"{label} did not reach a cancelled terminal event") from exc
    finally:
        _terminate_process_tree(process, target)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        reader.join(timeout=5)

    stderr = process.stderr.read()
    combined = f"{''.join(all_lines)}\n{stderr}".lower()
    if any(marker in combined for marker in SENSITIVE_MARKERS):
        raise ValueError(f"{label} output contains a sensitive field")
    result = parse_cancelled_stream("".join(all_lines))
    if session != {
        "conversation_id": result["conversation_id"],
        "turn_id": result["turn_id"],
    }:
        raise ValueError(f"{label} terminal event changed the session")
    return result


def safe_failure_detail(stdout: str) -> str:
    try:
        payload = json.loads(stdout.strip())
    except json.JSONDecodeError:
        return "no safe structured error"
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return "no safe structured error"
    code = error.get("code")
    message = error.get("message")
    if not isinstance(code, str) or not isinstance(message, str):
        return "no safe structured error"
    detail = f"{code}: {message}"
    if any(marker in detail.lower() for marker in SENSITIVE_MARKERS):
        return "structured error redacted"
    return detail[:240]


def retryable_read_failure(error: ValueError) -> bool:
    return "TRANSPORT_ERROR" in str(error) or "failed with exit 50" in str(error)


def project_name(host: str, target: str, run_id: str) -> str:
    label = re.sub(r"[^A-Za-z0-9]+", " ", f"E2E {host} {target} {run_id}")
    return " ".join(label.split())[:40].rstrip()


def _run_read_only_probe(
    command: list[str],
    *,
    environment: dict[str, str],
    cwd: Path,
    label: str,
) -> subprocess.CompletedProcess[str]:
    last_error: ValueError | None = None
    for attempt in range(3):
        try:
            return _run(
                command,
                environment=environment,
                cwd=cwd,
                label=label,
            )
        except ValueError as exc:
            last_error = exc
            if not retryable_read_failure(exc) or attempt == 2:
                raise
            time.sleep(2)
    raise last_error or ValueError(f"{label} failed")


def _json_stdout(result: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} stdout is not JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} stdout must be an object")
    return payload


def _envelope_data(result: subprocess.CompletedProcess[str], label: str) -> Any:
    payload = _json_stdout(result, label)
    if payload.get("ok") is not True or payload.get("error") is not None:
        raise ValueError(f"{label} returned an error envelope")
    return payload.get("data")


def _host_environment(host: str, root: Path) -> dict[str, str]:
    if host == "codex":
        home = root / "codex-home"
        home.mkdir(parents=True, exist_ok=True)
        return {"CODEX_HOME": str(home)}
    home = root / "claude-home"
    home.mkdir(parents=True, exist_ok=True)
    return {"CLAUDE_CONFIG_DIR": str(home), "DISABLE_AUTOUPDATER": "1"}


def _host_executable(host: str) -> Path:
    command = "codex" if host == "codex" else "claude"
    executable = shutil.which(command)
    if executable is None:
        raise ValueError(f"{host} executable is unavailable")
    return Path(executable)


def _install_plugin(
    host: str,
    executable: Path,
    target: str,
    environment: dict[str, str],
    cwd: Path,
    marketplace: Path,
) -> None:
    if host == "codex":
        _run(
            host_command(
                executable,
                target,
                ["plugin", "marketplace", "add", str(marketplace), "--json"],
            ),
            environment=environment,
            cwd=cwd,
            label="Codex marketplace add",
        )
        _run(
            host_command(executable, target, ["plugin", "add", PLUGIN_ID, "--json"]),
            environment=environment,
            cwd=cwd,
            label="Codex plugin install",
        )
        return
    _run(
        host_command(
            executable,
            target,
            ["plugin", "marketplace", "add", str(marketplace), "--scope", "user"],
        ),
        environment=environment,
        cwd=cwd,
        label="Claude marketplace add",
    )
    _run(
        host_command(
            executable,
            target,
            ["plugin", "install", PLUGIN_ID, "--scope", "user"],
        ),
        environment=environment,
        cwd=cwd,
        label="Claude plugin install",
    )


def _installed_plugin(
    host: str,
    executable: Path,
    target: str,
    environment: dict[str, str],
    cwd: Path,
    root: Path,
    expected_version: str,
) -> Path:
    result = _run(
        host_command(executable, target, ["plugin", "list", "--json"]),
        environment=environment,
        cwd=cwd,
        label=f"{host} plugin list",
    )
    payload = json.loads(result.stdout)
    records = payload.get("installed") if host == "codex" else payload
    if not isinstance(records, list):
        raise ValueError(f"{host} plugin list has an unexpected shape")
    identifier = "pluginId" if host == "codex" else "id"
    record = next(
        (
            item
            for item in records
            if isinstance(item, dict) and item.get(identifier) == PLUGIN_ID
        ),
        None,
    )
    if record is None or record.get("version") != expected_version:
        raise ValueError(f"{host} did not install the expected plugin version")
    if host == "codex":
        installed = (
            root
            / "codex-home"
            / "plugins"
            / "cache"
            / MARKETPLACE_NAME
            / PLUGIN_NAME
            / expected_version
        )
    else:
        installed = Path(str(record.get("installPath", "")))
    installed = installed.resolve()
    if not installed.is_relative_to(root.resolve()):
        raise ValueError(f"{host} installed outside the isolated host directory")
    return installed


def _launcher(installed: Path, target: str) -> Path:
    name = "vivago-agent.cmd" if target.startswith("windows-") else "vivago-agent"
    launcher = installed / "skills" / PLUGIN_NAME / "scripts" / name
    if not launcher.is_file():
        raise ValueError("installed plugin launcher is missing")
    return launcher


def _run_host_case(
    *,
    host: str,
    target: str,
    marketplace: Path,
    version: str,
    run_id: str,
    root: Path,
) -> dict[str, Any]:
    host_root = root / host
    host_root.mkdir()
    work = host_root / "work"
    work.mkdir()
    environment = _host_environment(host, host_root)
    executable = _host_executable(host)
    _install_plugin(host, executable, target, environment, work, marketplace)
    installed = _installed_plugin(
        host,
        executable,
        target,
        environment,
        work,
        host_root,
        version,
    )
    launcher = _launcher(installed, target)

    doctor = _envelope_data(
        _run(
            launcher_command(launcher, target, ["--json", "doctor"]),
            environment=environment,
            cwd=work,
            label=f"{host} doctor",
        ),
        f"{host} doctor",
    )
    checks = doctor.get("checks") if isinstance(doctor, dict) else None
    credentials = checks.get("credentials") if isinstance(checks, dict) else None
    if not isinstance(credentials, dict) or credentials.get("logged_in") is not True:
        raise ValueError(f"{host} did not load the seeded credential")

    status = _envelope_data(
        _run(
            launcher_command(launcher, target, ["--json", "auth", "status"]),
            environment=environment,
            cwd=work,
            label=f"{host} auth status",
        ),
        f"{host} auth status",
    )
    if not isinstance(status, dict) or status.get("logged_in") is not True:
        raise ValueError(f"{host} authentication status is not logged in")

    _envelope_data(
        _run_read_only_probe(
            launcher_command(
                launcher,
                target,
                ["--json", "project", "list", "--page-size", "1"],
            ),
            environment=environment,
            cwd=work,
            label=f"{host} project list probe",
        ),
        f"{host} project list probe",
    )
    time.sleep(2)

    case_project_name = project_name(host, target, run_id)
    project = _envelope_data(
        _run(
            launcher_command(
                launcher,
                target,
                ["--json", "project", "create", "--name", case_project_name],
            ),
            environment=environment,
            cwd=work,
            label=f"{host} project create",
        ),
        f"{host} project create",
    )
    project_data = project.get("data") if isinstance(project, dict) else None
    project_id = project_data.get("project_id") if isinstance(project_data, dict) else None
    if not isinstance(project_id, str) or not SAFE_IDENTIFIER.fullmatch(project_id):
        raise ValueError(f"{host} project create returned an invalid identifier")

    stream = _run(
        launcher_command(
            launcher,
            target,
            [
                "--jsonl",
                "ask",
                "--project-id",
                project_id,
                "--prompt",
                "Reply with exactly: VivagoAgent hosted L3 text check passed. Do not use media tools.",
            ],
        ),
        environment=environment,
        cwd=work,
        label=f"{host} text task",
    )
    stream_result = _parse_finished_for(stream.stdout, f"{host} text task")

    project_link = _envelope_data(
        _run(
            launcher_command(
                launcher,
                target,
                [
                    "--json",
                    "project",
                    "link",
                    "--project-id",
                    project_id,
                    "--conversation-id",
                    stream_result["conversation_id"],
                ],
            ),
            environment=environment,
            cwd=work,
            label=f"{host} project link",
        ),
        f"{host} project link",
    )
    project_link_host = validate_project_link(
        project_link,
        project_id,
        stream_result["conversation_id"],
    )

    attachment_path = work / "hosted-l3-attachment.png"
    write_attachment_fixture(attachment_path)
    attachment_stream = _run(
        launcher_command(
            launcher,
            target,
            [
                "--jsonl",
                "ask",
                "--conversation-id",
                stream_result["conversation_id"],
                "--file",
                str(attachment_path),
                "--prompt",
                (
                    "Inspect the attached image. Reply only with the three vertical band "
                    "colors from left to right, as lowercase words separated by commas. "
                    "Do not use media generation tools."
                ),
            ],
        ),
        environment=environment,
        cwd=work,
        label=f"{host} attachment task",
    )
    attachment_result = _parse_finished_for(
        attachment_stream.stdout,
        f"{host} attachment task",
    )
    if attachment_result["conversation_id"] != stream_result["conversation_id"]:
        raise ValueError(f"{host} attachment task changed the conversation")
    if not stream_text_matches(attachment_stream.stdout, "red, green, blue"):
        raise ValueError(f"{host} did not read the uploaded attachment correctly")

    clarification_stream = _run(
        launcher_command(
            launcher,
            target,
            [
                "--jsonl",
                "ask",
                "--conversation-id",
                stream_result["conversation_id"],
                "--prompt",
                (
                    "Before doing any work, ask exactly: What color should the test banner use? "
                    "Do not use tools."
                ),
            ],
        ),
        environment=environment,
        cwd=work,
        label=f"{host} clarification request",
    )
    clarification_result = _parse_finished_for(
        clarification_stream.stdout,
        f"{host} clarification request",
    )
    if not stream_text_matches(
        clarification_stream.stdout,
        "What color should the test banner use?",
    ):
        raise ValueError(f"{host} did not request the expected clarification")

    clarification_answer_stream = _run(
        launcher_command(
            launcher,
            target,
            [
                "--jsonl",
                "ask",
                "--conversation-id",
                stream_result["conversation_id"],
                "--prompt",
                "Use blue. Reply exactly: The test banner color is blue. Do not use tools.",
            ],
        ),
        environment=environment,
        cwd=work,
        label=f"{host} clarification answer",
    )
    clarification_answer_result = _parse_finished_for(
        clarification_answer_stream.stdout,
        f"{host} clarification answer",
    )
    if not stream_text_matches(
        clarification_answer_stream.stdout,
        "The test banner color is blue.",
    ):
        raise ValueError(f"{host} did not continue after clarification")
    if any(
        result["conversation_id"] != stream_result["conversation_id"]
        for result in (clarification_result, clarification_answer_result)
    ):
        raise ValueError(f"{host} clarification round trip changed the conversation")

    resume_checkpoint = _interrupt_after_checkpoint(
        launcher_command(
            launcher,
            target,
            [
                "--jsonl",
                "ask",
                "--conversation-id",
                stream_result["conversation_id"],
                "--prompt",
                (
                    "Output the integers 1 through 500, one integer per line. "
                    "Use plain text only and do not use tools."
                ),
            ],
        ),
        target=target,
        environment=environment,
        cwd=work,
        label=f"{host} interrupted text task",
    )
    if resume_checkpoint["conversation_id"] != stream_result["conversation_id"]:
        raise ValueError(f"{host} interrupted task changed the conversation")
    resumed_stream = _run(
        launcher_command(
            launcher,
            target,
            [
                "--jsonl",
                "resume",
                "--turn-id",
                resume_checkpoint["turn_id"],
                "--last-event-id",
                resume_checkpoint["last_event_id"],
            ],
        ),
        environment=environment,
        cwd=work,
        label=f"{host} resumed text task",
        timeout=300,
    )
    try:
        resume_result = parse_resumed_stream(
            resumed_stream.stdout,
            stream_result["conversation_id"],
            resume_checkpoint["turn_id"],
        )
    except ValueError as exc:
        raise ValueError(f"{host} resumed text task: {exc}") from exc

    image_stream = _run(
        launcher_command(
            launcher,
            target,
            [
                "--jsonl",
                "ask",
                "--conversation-id",
                stream_result["conversation_id"],
                "--prompt",
                (
                    "Generate one simple square test image of a blue circle centered on a plain "
                    "white background. Use the image generation tool and return the final image."
                ),
            ],
        ),
        environment=environment,
        cwd=work,
        label=f"{host} image artifact task",
        timeout=600,
    )
    image_result = _parse_finished_for(image_stream.stdout, f"{host} image artifact task")
    if image_result["conversation_id"] != stream_result["conversation_id"]:
        raise ValueError(f"{host} image artifact task changed the conversation")
    image_content_id = extract_image_artifact(image_stream.stdout)

    preview = _envelope_data(
        _run(
            launcher_command(
                launcher,
                target,
                [
                    "--json",
                    "artifact",
                    "preview",
                    "--media-type",
                    "image",
                    "--content-id",
                    image_content_id,
                ],
            ),
            environment=environment,
            cwd=work,
            label=f"{host} artifact preview",
            timeout=300,
        ),
        f"{host} artifact preview",
    )
    preview_bytes, preview_content_type, preview_path = validate_artifact_file(preview)
    if not preview_path.parent.name.startswith("vivago-agent-preview-"):
        raise ValueError(f"{host} artifact preview used an unexpected directory")
    shutil.rmtree(preview_path.parent)

    download_path = work / "hosted-l3-generated.png"
    downloaded = _envelope_data(
        _run(
            launcher_command(
                launcher,
                target,
                [
                    "--json",
                    "artifact",
                    "download",
                    "--media-type",
                    "image",
                    "--content-id",
                    image_content_id,
                    "--output",
                    str(download_path),
                ],
            ),
            environment=environment,
            cwd=work,
            label=f"{host} artifact download",
            timeout=300,
        ),
        f"{host} artifact download",
    )
    download_bytes, download_content_type, _ = validate_artifact_file(
        downloaded,
        download_path,
    )
    if preview_content_type != download_content_type or preview_bytes != download_bytes:
        raise ValueError(f"{host} preview and download returned different artifacts")

    cancelled_result = _cancel_active_stream(
        launcher_command(
            launcher,
            target,
            [
                "--jsonl",
                "ask",
                "--conversation-id",
                stream_result["conversation_id"],
                "--prompt",
                (
                    "Generate one simple square test image showing three vertical color bands "
                    "with the text L3 CANCEL. Use the image generation tool."
                ),
            ],
        ),
        lambda conversation_id, turn_id: launcher_command(
            launcher,
            target,
            [
                "--json",
                "cancel",
                "--conversation-id",
                conversation_id,
                "--turn-id",
                turn_id,
            ],
        ),
        target=target,
        environment=environment,
        cwd=work,
        label=f"{host} cancellation task",
    )
    if cancelled_result["conversation_id"] != stream_result["conversation_id"]:
        raise ValueError(f"{host} cancellation task changed the conversation")

    completed_turn_ids = {
        stream_result["turn_id"],
        attachment_result["turn_id"],
        clarification_result["turn_id"],
        clarification_answer_result["turn_id"],
        resume_result["turn_id"],
        image_result["turn_id"],
    }
    history_verified = False
    for attempt in range(5):
        history = _envelope_data(
            _run_read_only_probe(
                launcher_command(
                    launcher,
                    target,
                    [
                        "--json",
                        "history",
                        "--conversation-id",
                        stream_result["conversation_id"],
                    ],
                ),
                environment=environment,
                cwd=work,
                label=f"{host} history",
            ),
            f"{host} history",
        )
        history_data = history.get("data") if isinstance(history, dict) else None
        turns = history_data.get("turns") if isinstance(history_data, dict) else None
        matching = [
            item
            for item in turns or []
            if isinstance(item, dict) and item.get("turn_id") in completed_turn_ids
        ]
        cancelled = [
            item
            for item in turns or []
            if isinstance(item, dict) and item.get("turn_id") == cancelled_result["turn_id"]
        ]
        if (
            len(matching) == len(completed_turn_ids)
            and all(item.get("status") == "completed" for item in matching)
            and len(cancelled) == 1
            and cancelled[0].get("status") == "cancelled"
        ):
            history_verified = True
            break
        if attempt < 4:
            time.sleep(2)
    if not history_verified:
        raise ValueError(f"{host} history did not persist completed and cancelled turns")

    restarted_installed = _installed_plugin(
        host,
        _host_executable(host),
        target,
        environment,
        work,
        host_root,
        version,
    )
    if restarted_installed != installed:
        raise ValueError(f"{host} restart resolved a different plugin installation")
    restarted_status = _envelope_data(
        _run(
            launcher_command(launcher, target, ["--json", "auth", "status"]),
            environment=environment,
            cwd=work,
            label=f"{host} restarted auth status",
        ),
        f"{host} restarted auth status",
    )
    if not isinstance(restarted_status, dict) or restarted_status.get("logged_in") is not True:
        raise ValueError(f"{host} did not retain the credential after restart")

    return {
        "host": host,
        "plugin_version": version,
        "credential_backend": str(status.get("backend", "")),
        "project_id": project_id,
        **stream_result,
        "attachment_turn_id": attachment_result["turn_id"],
        "clarification_turn_id": clarification_result["turn_id"],
        "clarification_answer_turn_id": clarification_answer_result["turn_id"],
        "resumed_turn_id": resume_result["turn_id"],
        "artifact_turn_id": image_result["turn_id"],
        "cancelled_turn_id": cancelled_result["turn_id"],
        "artifact_bytes": download_bytes,
        "artifact_content_type": download_content_type,
        "project_link_host": project_link_host,
        "history_status": "completed",
        "checks": {
            "login": "NOT_RUN",
            "refresh": "NOT_RUN",
            "logout_relogin": "NOT_RUN",
            "plugin_install": "PASS",
            "credential_load": "PASS",
            "text_task": "PASS",
            "attachment": "PASS",
            "same_conversation_continue": "PASS",
            "sse_interruption_resume": "PASS",
            "cancel": "PASS",
            "project_link": "PASS",
            "history": "PASS",
            "host_restart_credential": "PASS",
            "input_required": "PASS_AUTOMATED_CLARIFICATION_ROUND_TRIP",
            "artifact_preview_download": "PASS",
            "image_generation": "PASS",
            "upgrade_rollback": "PASS_IN_L2_RELEASE_GATE",
        },
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    if not args.marketplace.is_dir():
        raise ValueError("Marketplace directory does not exist")
    if not REVISION.fullmatch(args.source_revision):
        raise ValueError("source revision must be a full Git SHA")
    if not SAFE_IDENTIFIER.fullmatch(args.run_id):
        raise ValueError("run id contains unsupported characters")
    target = detect_native_target()
    if target != args.expected_target:
        raise ValueError("runner target does not match the requested target")
    plugin = args.marketplace / "plugins" / PLUGIN_NAME
    version = (plugin / "VERSION").read_text(encoding="utf-8").strip()
    build_info = json.loads((plugin / "BUILD_INFO.json").read_text(encoding="utf-8"))
    if version != args.expected_version:
        raise ValueError("Marketplace version does not match")
    if str(build_info.get("source_revision", "")).lower() != args.source_revision.lower():
        raise ValueError("Marketplace source revision does not match")
    if build_info.get("profile") != "dev" or build_info.get("channel") != "dev":
        raise ValueError("Marketplace is not a development build")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    root = args.report.parent / f"runtime-{target}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    try:
        cases = [
            _run_host_case(
                host=host,
                target=target,
                marketplace=args.marketplace.resolve(),
                version=version,
                run_id=args.run_id,
                root=root,
            )
            for host in HOSTS
        ]
    except Exception:
        raise
    else:
        shutil.rmtree(root)
    report = {
        "ok": True,
        "target": target,
        "version": version,
        "source_revision": args.source_revision.lower(),
        "profile": "dev",
        "environment": "overseas-test",
        "authentication_scope": "one-time-access-only",
        "cases": cases,
    }
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def write_failure_report(args: argparse.Namespace, message: str) -> None:
    report = {
        "ok": False,
        "target": args.expected_target,
        "version": args.expected_version,
        "source_revision": args.source_revision.lower(),
        "failure": message,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = arguments(argv)
    try:
        report = verify(args)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        write_failure_report(args, str(exc))
        print("error: hosted L3 verification failed", file=sys.stderr)
        return 1
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
