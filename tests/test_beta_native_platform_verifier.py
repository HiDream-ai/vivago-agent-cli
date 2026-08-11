from __future__ import annotations

import json
import platform
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_beta_native_platform.py"
TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)
VERSION = "0.3.0-beta.9"
REVISION = "b" * 40


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


def _marketplace_archive(
    root: Path,
    *,
    channel: str = "beta",
    profile: str = "prod",
    environment: str = "overseas-production",
) -> Path:
    target = _current_target()
    reported_os, reported_arch = target.split("-", 1)
    marketplace = root / "marketplace"
    plugin = marketplace / "plugins" / "vivago-agent-cli"
    launcher_dir = plugin / "skills" / "vivago-agent-cli" / "scripts"
    launcher_dir.mkdir(parents=True)
    (plugin / "BUILD_INFO.json").write_text(
        json.dumps(
            {
                "version": VERSION,
                "source_revision": REVISION,
                "channel": channel,
                "profile": profile,
                "targets": list(TARGETS),
            }
        ),
        encoding="utf-8",
    )
    doctor = {
        "ok": False,
        "data": {
            "ok": False,
            "checks": {
                "build": {
                    "ok": True,
                    "version": VERSION,
                    "git_sha": REVISION,
                    "channel": channel,
                },
                "platform": {
                    "ok": True,
                    "os": reported_os,
                    "arch": reported_arch,
                },
                "environment": {
                    "ok": True,
                    "profile": profile,
                    "target": environment,
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
    }
    if sys.platform == "win32":
        launcher = launcher_dir / "vivago-agent.cmd"
        launcher.write_text(
            "@echo off\r\n"
            "if \"%2\"==\"version\" (echo {\"ok\":true,\"data\":{\"version\":\""
            + VERSION
            + "\"},\"error\":null}& exit /b 0)\r\n"
            "echo "
            + json.dumps(doctor, separators=(",", ":"))
            + "\r\nexit /b 40\r\n",
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
            + json.dumps(doctor, separators=(",", ":"))
            + "'\nexit 40\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)

    archive = root / "marketplace.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for path in sorted(marketplace.rglob("*")):
            bundle.add(path, arcname=path.relative_to(marketplace))
    return archive


def _run(archive: Path, target: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--archive",
            str(archive),
            "--expected-target",
            target or _current_target(),
            "--version",
            VERSION,
            "--source-revision",
            REVISION,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class BetaNativePlatformVerifierTests(unittest.TestCase):
    def test_accepts_production_beta_without_login(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = _run(_marketplace_archive(Path(directory)))

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["profile"], "prod")
        self.assertEqual(payload["environment"], "overseas-production")
        self.assertEqual(payload["channel"], "beta")

    def test_rejects_development_build_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = _marketplace_archive(
                Path(directory),
                channel="dev",
                profile="dev",
                environment="overseas-test",
            )
            result = _run(archive)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BUILD_INFO.json", result.stderr)

    def test_rejects_doctor_reporting_non_production_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = _marketplace_archive(Path(directory), environment="overseas-test")
            result = _run(archive)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overseas production profile", result.stderr)

    def test_rejects_runner_target_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = _marketplace_archive(Path(directory))
            wrong_target = next(target for target in TARGETS if target != _current_target())
            result = _run(archive, wrong_target)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runner target mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
