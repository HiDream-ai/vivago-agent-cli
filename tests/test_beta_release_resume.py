from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_STATE = REPO_ROOT / "scripts" / "validate_beta_release_state.py"
MARKETPLACE_STATE = REPO_ROOT / "scripts" / "validate_beta_marketplace_update.py"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BetaReleaseResumeTests(unittest.TestCase):
    def _release_inputs(self, root: Path) -> tuple[Path, Path, Path]:
        archive = root / "vivago-beta-marketplace.tar.gz"
        sbom = root / "SBOM.spdx.json"
        checksums = root / "SHA256SUMS"
        archive.write_bytes(b"archive")
        sbom.write_bytes(b"sbom")
        checksums.write_bytes(b"checksums")
        return archive, sbom, checksums

    def _run_release_state(
        self,
        root: Path,
        *,
        revision: str,
        tag_revision: str | None = None,
        release: dict[str, object] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        archive, sbom, checksums = self._release_inputs(root)
        command = [
            sys.executable,
            str(RELEASE_STATE),
            "--version",
            "0.3.0-beta.1",
            "--source-revision",
            revision,
            "--archive",
            str(archive),
            "--sbom",
            str(sbom),
            "--checksums",
            str(checksums),
        ]
        if tag_revision is not None:
            command.extend(("--tag-revision", tag_revision))
        if release is not None:
            release_path = root / "release.json"
            release_path.write_text(json.dumps(release), encoding="utf-8")
            command.extend(("--release-json", str(release_path)))
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def _matching_release(self, root: Path, revision: str) -> dict[str, object]:
        archive, sbom, checksums = self._release_inputs(root)
        return {
            "tagName": "v0.3.0-beta.1",
            "targetCommitish": revision,
            "isPrerelease": True,
            "isDraft": False,
            "assets": [
                {"name": archive.name, "digest": f"sha256:{_digest(archive)}"},
                {"name": sbom.name, "digest": f"sha256:{_digest(sbom)}"},
                {"name": checksums.name, "digest": f"sha256:{_digest(checksums)}"},
            ],
        }

    def test_fresh_release_can_create_tag_and_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run_release_state(Path(directory), revision="a" * 40)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "create_release")

    def test_matching_existing_release_can_resume_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = "b" * 40
            release = self._matching_release(root, revision)
            result = self._run_release_state(
                root,
                revision=revision,
                tag_revision=revision,
                release=release,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "resume_marketplace")

    def test_existing_tag_without_release_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run_release_state(
                Path(directory),
                revision="c" * 40,
                tag_revision="c" * 40,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("existing tag requires", result.stderr)

    def test_resume_rejects_different_tag_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = "d" * 40
            result = self._run_release_state(
                root,
                revision=revision,
                tag_revision="e" * 40,
                release=self._matching_release(root, revision),
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tag revision", result.stderr)

    def test_resume_rejects_changed_release_asset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = "f" * 40
            release = self._matching_release(root, revision)
            release["assets"][0]["digest"] = "sha256:" + "0" * 64
            result = self._run_release_state(
                root,
                revision=revision,
                tag_revision=revision,
                release=release,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("asset digest", result.stderr)


class BetaMarketplaceUpdateTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        *,
        candidate_version: str = "0.3.0-beta.2",
        candidate_revision: str = "a" * 40,
        existing: dict[str, object] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(MARKETPLACE_STATE),
            "--candidate-version",
            candidate_version,
            "--candidate-revision",
            candidate_revision,
        ]
        if existing is not None:
            path = root / "BUILD_INFO.json"
            path.write_text(json.dumps(existing), encoding="utf-8")
            command.extend(("--existing-build-info", str(path)))
        return subprocess.run(command, capture_output=True, text=True, check=False)

    @staticmethod
    def _existing(version: str, revision: str) -> dict[str, object]:
        return {
            "version": version,
            "source_revision": revision,
            "channel": "beta",
            "profile": "prod",
        }

    def test_missing_marketplace_branch_can_be_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(Path(directory))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "initialize")

    def test_same_version_and_revision_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(
                Path(directory),
                existing=self._existing("0.3.0-beta.2", "a" * 40),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "already_current")

    def test_newer_candidate_can_fast_forward_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(
                Path(directory),
                existing=self._existing("0.3.0-beta.1", "b" * 40),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "update")

    def test_same_version_with_different_revision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(
                Path(directory),
                existing=self._existing("0.3.0-beta.2", "b" * 40),
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different source revision", result.stderr)

    def test_old_retry_cannot_overwrite_newer_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(
                Path(directory),
                candidate_version="0.3.0-beta.1",
                existing=self._existing("0.3.0-beta.2", "b" * 40),
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("newer Beta", result.stderr)


if __name__ == "__main__":
    unittest.main()
