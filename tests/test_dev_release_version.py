from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_dev_release_version.py"


class DevReleaseVersionTests(unittest.TestCase):
    def test_accepts_numeric_dev_release_version(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "0.3.0-dev.4"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"version":"0.3.0-dev.4"', result.stdout)

    def test_rejects_versions_outside_numeric_dev_channel(self) -> None:
        for version in (
            "v0.3.0-dev.4",
            "0.3.0-dev.foo",
            "0.3.0-beta.4",
            "0.3.0",
        ):
            with self.subTest(version=version):
                result = subprocess.run(
                    [sys.executable, str(VALIDATOR), version],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("X.Y.Z-dev.N", result.stderr)


if __name__ == "__main__":
    unittest.main()
