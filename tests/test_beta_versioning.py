from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "derive_previous_beta_version.py"


def _derive(version: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--version", version],
        capture_output=True,
        text=True,
        check=False,
    )


class BetaVersioningTests(unittest.TestCase):
    def test_decrements_beta_sequence_when_possible(self) -> None:
        result = _derive("0.3.0-beta.9")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "0.3.0-beta.8")

    def test_beta_one_uses_a_lower_synthetic_base_version(self) -> None:
        result = _derive("0.3.0-beta.1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "0.2.999999-beta.999999")

    def test_handles_major_boundary(self) -> None:
        result = _derive("1.0.0-beta.1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "0.999999.999999-beta.999999")

    def test_rejects_version_without_a_strictly_lower_beta(self) -> None:
        result = _derive("0.0.0-beta.1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no lower synthetic Beta version", result.stderr)

    def test_rejects_non_beta_version(self) -> None:
        result = _derive("0.3.0-dev.9")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("X.Y.Z-beta.N", result.stderr)


if __name__ == "__main__":
    unittest.main()
