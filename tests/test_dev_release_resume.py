from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_dev_release_state.py"


class DevReleaseResumeTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        *,
        revision: str,
        tag_revision: str | None = None,
        release: dict[str, object] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        archive = root / "vivago-dev-marketplace.tar.gz"
        archive.write_bytes(b"archive")
        command = [
            sys.executable,
            str(VALIDATOR),
            "--version",
            "0.3.0-dev.9",
            "--source-revision",
            revision,
            "--archive",
            str(archive),
        ]
        if tag_revision is not None:
            command.extend(("--tag-revision", tag_revision))
        if release is not None:
            release_path = root / "release.json"
            release_path.write_text(json.dumps(release), encoding="utf-8")
            command.extend(("--release-json", str(release_path)))
        return subprocess.run(command, capture_output=True, text=True, check=False)

    @staticmethod
    def _matching_release(root: Path, revision: str) -> dict[str, object]:
        archive = root / "vivago-dev-marketplace.tar.gz"
        archive.write_bytes(b"archive")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        return {
            "tagName": "v0.3.0-dev.9",
            "targetCommitish": revision,
            "isPrerelease": True,
            "isDraft": False,
            "assets": [
                {
                    "name": archive.name,
                    "digest": f"sha256:{digest}",
                }
            ],
        }

    def test_fresh_dev_release_can_create_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(Path(directory), revision="a" * 40)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "create_release")

    def test_matching_existing_dev_release_can_resume_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = "b" * 40
            result = self._run(
                root,
                revision=revision,
                tag_revision=revision,
                release=self._matching_release(root, revision),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "resume_marketplace")


if __name__ == "__main__":
    unittest.main()
