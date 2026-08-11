from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)


def _assembled_marketplace(root: Path) -> Path:
    binary_root = root / "binaries"
    for target in TARGETS:
        target_dir = binary_root / target
        target_dir.mkdir(parents=True)
        name = "vivago-agent.exe" if target.startswith("windows-") else "vivago-agent"
        binary = target_dir / name
        binary.write_bytes(
            (
                f"fake-{target} 0.3.0-dev.9 {'a' * 40} "
                "https://dev.vivago.ai/agent/login"
            ).encode()
        )
        binary.chmod(0o755)
    marketplace = root / "marketplace"
    assembled = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "assemble_go_distribution.py"),
            "--plugin-template",
            str(REPO_ROOT / "plugin"),
            "--binary-root",
            str(binary_root),
            "--output",
            str(marketplace),
            "--version",
            "0.3.0-dev.9",
            "--source-revision",
            "a" * 40,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if assembled.returncode != 0:
        raise AssertionError(assembled.stderr)
    return marketplace


class DevDistributionVerifierTests(unittest.TestCase):
    def test_accepts_complete_dev_marketplace_with_valid_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marketplace = _assembled_marketplace(Path(directory))
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "verify_dev_distribution.py"),
                    "--marketplace",
                    str(marketplace),
                    "--version",
                    "0.3.0-dev.9",
                    "--source-revision",
                    "a" * 40,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"ok":true', result.stdout)

    def test_rejects_production_endpoint_even_when_checksum_was_not_updated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marketplace = _assembled_marketplace(Path(directory))
            skill = (
                marketplace
                / "plugins"
                / "vivago-agent-cli"
                / "skills"
                / "vivago-agent-cli"
                / "SKILL.md"
            )
            skill.write_text(
                skill.read_text(encoding="utf-8") + "\nhttps://vivago.ai/agent/login\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "verify_dev_distribution.py"),
                    "--marketplace",
                    str(marketplace),
                    "--version",
                    "0.3.0-dev.9",
                    "--source-revision",
                    "a" * 40,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("forbidden environment marker", result.stderr)


if __name__ == "__main__":
    unittest.main()
