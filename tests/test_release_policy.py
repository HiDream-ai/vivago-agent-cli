from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_VALIDATOR = REPO_ROOT / "scripts" / "validate_dev_release_policy.py"
BETA_VALIDATOR = REPO_ROOT / "scripts" / "validate_beta_release_policy.py"


def _run(script: Path, *, version: str, repository: str, ref: str, revision: str):
    return subprocess.run(
        [
            sys.executable,
            str(script),
            "--version",
            version,
            "--repository",
            repository,
            "--ref",
            ref,
            "--source-revision",
            revision,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class ReleasePolicyTests(unittest.TestCase):
    def test_dev_policy_accepts_personal_feature_revision(self) -> None:
        result = _run(
            DEV_VALIDATOR,
            version="0.3.0-dev.7",
            repository="ChaoXia-Beginer/vivago-agent-cli",
            ref="refs/heads/feature/beta-build",
            revision="a" * 40,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '{"ok":true,"channel":"dev"}')

    def test_dev_policy_rejects_company_repository(self) -> None:
        result = _run(
            DEV_VALIDATOR,
            version="0.3.0-dev.7",
            repository="HiDream-ai/vivago-agent-cli",
            ref="refs/heads/main",
            revision="b" * 40,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("development repository", result.stderr)

    def test_dev_policy_rejects_beta_version(self) -> None:
        result = _run(
            DEV_VALIDATOR,
            version="0.3.0-beta.1",
            repository="ChaoXia-Beginer/vivago-agent-cli",
            ref="refs/heads/main",
            revision="c" * 40,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("development version", result.stderr)

    def test_beta_policy_accepts_company_main_revision(self) -> None:
        result = _run(
            BETA_VALIDATOR,
            version="0.3.0-beta.1",
            repository="HiDream-ai/vivago-agent-cli",
            ref="refs/heads/main",
            revision="d" * 40,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '{"ok":true,"channel":"beta"}')

    def test_beta_policy_rejects_personal_repository(self) -> None:
        result = _run(
            BETA_VALIDATOR,
            version="0.3.0-beta.1",
            repository="ChaoXia-Beginer/vivago-agent-cli",
            ref="refs/heads/main",
            revision="e" * 40,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("company repository", result.stderr)

    def test_beta_policy_rejects_feature_branch(self) -> None:
        result = _run(
            BETA_VALIDATOR,
            version="0.3.0-beta.1",
            repository="HiDream-ai/vivago-agent-cli",
            ref="refs/heads/feature/beta-build",
            revision="f" * 40,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refs/heads/main", result.stderr)

    def test_beta_policy_rejects_dev_version(self) -> None:
        result = _run(
            BETA_VALIDATOR,
            version="0.3.0-dev.7",
            repository="HiDream-ai/vivago-agent-cli",
            ref="refs/heads/main",
            revision="1" * 40,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("beta version", result.stderr)

    def test_policies_reject_non_full_revision(self) -> None:
        for script, version, repository in (
            (
                DEV_VALIDATOR,
                "0.3.0-dev.7",
                "ChaoXia-Beginer/vivago-agent-cli",
            ),
            (
                BETA_VALIDATOR,
                "0.3.0-beta.1",
                "HiDream-ai/vivago-agent-cli",
            ),
        ):
            with self.subTest(script=script.name):
                result = _run(
                    script,
                    version=version,
                    repository=repository,
                    ref="refs/heads/main",
                    revision="abc123",
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("40-character Git SHA", result.stderr)


if __name__ == "__main__":
    unittest.main()
