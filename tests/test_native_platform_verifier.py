from __future__ import annotations

import importlib.util
import json
import platform
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_native_platform.py"
TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)
VERSION = "0.3.0-dev.9"
REVISION = "a" * 40


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_native_platform", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load native platform verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _current_target() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    operating_system = {"darwin": "darwin", "linux": "linux", "windows": "windows"}[system]
    architecture = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
    return f"{operating_system}-{architecture}"


def _credential_backend(target: str) -> str:
    if target.startswith("darwin-"):
        return "keychain"
    if target.startswith("windows-"):
        return "credential-manager"
    return "file"


def _marketplace_archive(root: Path, *, reported_target: str | None = None) -> Path:
    target = _current_target()
    reported_target = reported_target or target
    reported_os, reported_arch = reported_target.split("-", 1)
    marketplace = root / "marketplace"
    plugin = marketplace / "plugins" / "vivago-agent-cli"
    launcher_dir = plugin / "skills" / "vivago-agent-cli" / "scripts"
    launcher_dir.mkdir(parents=True)
    (plugin / "BUILD_INFO.json").write_text(
        json.dumps(
            {
                "version": VERSION,
                "source_revision": REVISION,
                "channel": "dev",
                "profile": "dev",
                "targets": list(TARGETS),
            }
        ),
        encoding="utf-8",
    )
    if sys.platform == "win32":
        launcher = launcher_dir / "vivago-agent.cmd"
        launcher.write_text(
            "@echo off\r\n"
            "if \"%2\"==\"version\" (echo {\"ok\":true,\"data\":{\"version\":\""
            + VERSION
            + "\"},\"error\":null}& exit /b 0)\r\n"
            "echo {\"ok\":false,\"data\":{\"ok\":false,\"checks\":{"
            "\"build\":{\"ok\":true,\"version\":\""
            + VERSION
            + "\",\"git_sha\":\""
            + REVISION
            + "\",\"channel\":\"dev\"},"
            "\"platform\":{\"ok\":true,\"os\":\""
            + reported_os
            + "\",\"arch\":\""
            + reported_arch
            + "\"},"
            "\"environment\":{\"ok\":true,\"profile\":\"dev\",\"target\":\"overseas-test\"},"
            "\"credentials\":{\"ok\":false,\"backend\":\""
            + _credential_backend(target)
            + "\",\"logged_in\":false}}},"
            "\"error\":{\"code\":\"DEPENDENCY_MISSING\",\"message\":\"one or more checks failed\"}}\r\n"
            "exit /b 40\r\n",
            encoding="utf-8",
        )
    else:
        launcher = launcher_dir / "vivago-agent"
        launcher.write_text(
            "#!/bin/sh\n"
            "if [ \"$2\" = version ]; then\n"
            f"  printf '%s\\n' '{{\"ok\":true,\"data\":{{\"version\":\"{VERSION}\"}},\"error\":null}}'\n"
            "  exit 0\n"
            "fi\n"
            "printf '%s\\n' '"
            + json.dumps(
                {
                    "ok": False,
                    "data": {
                        "ok": False,
                        "checks": {
                            "build": {
                                "ok": True,
                                "version": VERSION,
                                "git_sha": REVISION,
                                "channel": "dev",
                            },
                            "platform": {
                                "ok": True,
                                "os": reported_os,
                                "arch": reported_arch,
                            },
                            "environment": {
                                "ok": True,
                                "profile": "dev",
                                "target": "overseas-test",
                            },
                            "credentials": {
                                "ok": False,
                                "backend": _credential_backend(target),
                                "logged_in": False,
                            },
                        },
                    },
                    "error": {
                        "code": "DEPENDENCY_MISSING",
                        "message": "one or more checks failed",
                    },
                },
                separators=(",", ":"),
            )
            + "'\nexit 40\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)

    archive = root / "marketplace.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for path in sorted(marketplace.rglob("*")):
            bundle.add(path, arcname=path.relative_to(marketplace))
    return archive


class NativePlatformVerifierTests(unittest.TestCase):
    def test_windows_launcher_command_keeps_cmd_tokens_separate(self) -> None:
        verifier = _load_verifier()
        launcher = Path(r"C:\Program Files\Vivago Agent\vivago-agent.cmd")

        self.assertEqual(
            verifier._launcher_command(launcher, "version", "windows-amd64"),
            [
                "cmd.exe",
                "/d",
                "/c",
                "call",
                str(launcher),
                "--json",
                "version",
            ],
        )

    def test_supported_targets_match_the_public_beta_matrix(self) -> None:
        verifier = _load_verifier()

        self.assertEqual(verifier.TARGETS, TARGETS)
        self.assertEqual(verifier.detect_native_target(), _current_target())

    def test_accepts_native_launcher_even_when_doctor_reports_missing_login(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = _marketplace_archive(root)
            report = root / "report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--archive",
                    str(archive),
                    "--expected-target",
                    _current_target(),
                    "--version",
                    VERSION,
                    "--source-revision",
                    REVISION,
                    "--report",
                    str(report),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["target"], _current_target())
            self.assertEqual(payload["version"], VERSION)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8")), payload)
            self.assertNotIn("credentials", payload)

    def test_rejects_runner_that_does_not_match_expected_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = _marketplace_archive(Path(directory))
            wrong_target = next(target for target in TARGETS if target != _current_target())
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--archive",
                    str(archive),
                    "--expected-target",
                    wrong_target,
                    "--version",
                    VERSION,
                    "--source-revision",
                    REVISION,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runner target mismatch", result.stderr)

    def test_rejects_launcher_reporting_a_different_compiled_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrong_target = next(target for target in TARGETS if target != _current_target())
            archive = _marketplace_archive(root, reported_target=wrong_target)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--archive",
                    str(archive),
                    "--expected-target",
                    _current_target(),
                    "--version",
                    VERSION,
                    "--source-revision",
                    REVISION,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("launcher selected the wrong binary", result.stderr)


if __name__ == "__main__":
    unittest.main()
