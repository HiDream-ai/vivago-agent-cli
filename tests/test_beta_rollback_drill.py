from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_beta_rollback_drill import DrillError, _run_git  # noqa: E402

VALIDATOR = REPO_ROOT / "scripts" / "validate_beta_rollback_drill.py"
RUNNER = REPO_ROOT / "scripts" / "run_beta_rollback_drill.py"
INCIDENT_REVISION = "a" * 40
RECOVERY_REVISION = "b" * 40
BRANCH = "drill/marketplace-12345-1"


def _plan_command(**overrides: str) -> list[str]:
    values = {
        "incident-version": "0.3.0-beta.1",
        "recovery-version": "0.3.0-beta.2",
        "repository": "HiDream-ai/vivago-agent-cli",
        "ref": "refs/heads/main",
        "incident-revision": INCIDENT_REVISION,
        "recovery-revision": RECOVERY_REVISION,
        "branch": BRANCH,
        "run-id": "12345",
        "run-attempt": "1",
    }
    values.update(overrides)
    command = [sys.executable, str(VALIDATOR), "plan"]
    for name, value in values.items():
        command.extend((f"--{name}", value))
    return command


def _marketplace(root: Path, *, version: str, revision: str) -> Path:
    marketplace = root / version
    plugin = marketplace / "plugins" / "vivago-agent-cli"
    plugin.mkdir(parents=True)
    (plugin / "BUILD_INFO.json").write_text(
        json.dumps(
            {
                "version": version,
                "source_revision": revision,
                "channel": "beta",
                "profile": "prod",
            }
        ),
        encoding="utf-8",
    )
    (plugin / "launcher").write_text(version, encoding="utf-8")
    return marketplace


class BetaRollbackDrillPlanTests(unittest.TestCase):
    def test_accepts_company_main_with_strictly_newer_recovery(self) -> None:
        result = subprocess.run(
            _plan_command(), capture_output=True, text=True, check=False
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "run_drill")

    def test_rejects_non_company_repository(self) -> None:
        result = subprocess.run(
            _plan_command(repository="ChaoXia-Beginer/vivago-agent-cli"),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("company repository", result.stderr)

    def test_rejects_non_main_ref(self) -> None:
        result = subprocess.run(
            _plan_command(ref="refs/heads/feature/test"),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refs/heads/main", result.stderr)

    def test_rejects_same_incident_and_recovery_revision(self) -> None:
        result = subprocess.run(
            _plan_command(**{"recovery-revision": INCIDENT_REVISION}),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must differ", result.stderr)

    def test_rejects_recovery_version_that_is_not_newer(self) -> None:
        result = subprocess.run(
            _plan_command(**{"recovery-version": "0.3.0-beta.1"}),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("strictly newer", result.stderr)

    def test_rejects_recovery_version_from_another_release_line(self) -> None:
        result = subprocess.run(
            _plan_command(**{"recovery-version": "0.4.0-beta.2"}),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("same release line", result.stderr)

    def test_rejects_branch_not_derived_from_run_identity(self) -> None:
        result = subprocess.run(
            _plan_command(branch="marketplace"),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(BRANCH, result.stderr)


class BetaRollbackDrillRunnerTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        *,
        recovery_version: str = "0.3.0-beta.2",
        recovery_build_info_version: str = "0.3.0-beta.2",
        started_at: int | None = None,
        require_commit_signing: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        remote = root / "remote.git"
        source = root / "source"
        subprocess.run(
            ["git", "init", "--bare", str(remote)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "init", str(source)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "config", "user.name", "Rollback Drill Test"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "config",
                "user.email",
                "rollback-drill@example.invalid",
            ],
            check=True,
        )
        (source / "README.md").write_text("source", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(source), "add", "README.md"], check=True
        )
        subprocess.run(
            ["git", "-C", str(source), "commit", "-m", "initial"],
            check=True,
            capture_output=True,
            text=True,
        )
        if require_commit_signing:
            subprocess.run(
                ["git", "-C", str(source), "config", "commit.gpgsign", "true"],
                check=True,
            )
        subprocess.run(
            ["git", "-C", str(source), "remote", "add", "origin", str(remote)],
            check=True,
        )
        incident = _marketplace(
            root, version="0.3.0-beta.1", revision=INCIDENT_REVISION
        )
        recovery = _marketplace(
            root,
            version=recovery_build_info_version,
            revision=RECOVERY_REVISION,
        )
        report = root / "report.json"
        command = [
            sys.executable,
            str(RUNNER),
            "--incident-marketplace",
            str(incident),
            "--recovery-marketplace",
            str(recovery),
            "--incident-version",
            "0.3.0-beta.1",
            "--recovery-version",
            recovery_version,
            "--repository",
            "HiDream-ai/vivago-agent-cli",
            "--ref",
            "refs/heads/main",
            "--incident-revision",
            INCIDENT_REVISION,
            "--recovery-revision",
            RECOVERY_REVISION,
            "--branch",
            BRANCH,
            "--run-id",
            "12345",
            "--run-attempt",
            "1",
            "--remote",
            "origin",
            "--repository-root",
            str(source),
            "--started-at-epoch",
            str(started_at if started_at is not None else int(time.time())),
            "--report",
            str(report),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        result.report = report  # type: ignore[attr-defined]
        result.remote = remote  # type: ignore[attr-defined]
        return result

    def _remote_branch(self, result: subprocess.CompletedProcess[str]) -> str:
        remote = result.remote  # type: ignore[attr-defined]
        query = subprocess.run(
            ["git", "ls-remote", "--heads", str(remote), f"refs/heads/{BRANCH}"],
            check=True,
            capture_output=True,
            text=True,
        )
        return query.stdout.strip()

    def test_pushes_incident_then_recovery_and_removes_temporary_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(Path(directory))
            self.assertTrue(result.report.is_file(), result.stderr)  # type: ignore[attr-defined]
            report = json.loads(result.report.read_text(encoding="utf-8"))  # type: ignore[attr-defined]
            remote_branch = self._remote_branch(result)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["cleanup"], "deleted")
        self.assertEqual(report["recovery_parent"], report["incident_commit"])
        self.assertLessEqual(report["elapsed_seconds"], 1800)
        self.assertEqual(remote_branch, "")

    def test_cleans_remote_branch_when_recovery_metadata_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(
                Path(directory), recovery_build_info_version="0.3.0-beta.3"
            )
            remote_branch = self._remote_branch(result)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("recovery Marketplace metadata", result.stderr)
        self.assertEqual(remote_branch, "")

    def test_fails_when_recovery_exceeds_thirty_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(Path(directory), started_at=int(time.time()) - 1801)
            self.assertTrue(result.report.is_file(), result.stderr)  # type: ignore[attr-defined]
            report = json.loads(result.report.read_text(encoding="utf-8"))  # type: ignore[attr-defined]
            remote_branch = self._remote_branch(result)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(report["status"], "failed")
        self.assertGreater(report["elapsed_seconds"], 1800)
        self.assertEqual(report["cleanup"], "deleted")
        self.assertEqual(remote_branch, "")

    def test_git_failure_reports_safe_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", str(repository)], check=True, capture_output=True)
            with self.assertRaises(DrillError) as context:
                _run_git(repository, ["not-a-real-git-operation"])

        self.assertIn("git not-a-real-git-operation failed (exit", str(context.exception))

    def test_rollback_commits_ignore_global_signing_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(Path(directory), require_commit_signing=True)

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
