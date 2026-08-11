from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSEMBLER = REPO_ROOT / "scripts" / "assemble_beta_distribution.py"
VERIFIER = REPO_ROOT / "scripts" / "verify_beta_distribution.py"
TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)
VERSION = "0.3.0-beta.1"
REVISION = "a" * 40


def _write_binaries(root: Path, *, suffix: str = "") -> Path:
    binary_root = root / "binaries"
    for target in TARGETS:
        target_dir = binary_root / target
        target_dir.mkdir(parents=True)
        name = "vivago-agent.exe" if target.startswith("windows-") else "vivago-agent"
        binary = target_dir / name
        binary.write_bytes(
            (
                f"fake-{target} {VERSION} {REVISION} "
                f"https://vivago.ai/agent/login{suffix}"
            ).encode()
        )
        binary.chmod(0o755)
    return binary_root


def _assemble(root: Path) -> Path:
    marketplace = root / "marketplace"
    result = subprocess.run(
        [
            sys.executable,
            str(ASSEMBLER),
            "--plugin-template",
            str(REPO_ROOT / "plugin"),
            "--binary-root",
            str(_write_binaries(root)),
            "--output",
            str(marketplace),
            "--version",
            VERSION,
            "--source-revision",
            REVISION,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return marketplace


class BetaDistributionTests(unittest.TestCase):
    def test_assembler_creates_six_platform_production_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marketplace = _assemble(Path(directory))
            plugin = marketplace / "plugins" / "vivago-agent-cli"

            build_info = json.loads((plugin / "BUILD_INFO.json").read_text(encoding="utf-8"))
            self.assertEqual(
                build_info,
                {
                    "version": VERSION,
                    "source_revision": REVISION,
                    "channel": "beta",
                    "profile": "prod",
                    "targets": list(TARGETS),
                },
            )
            self.assertEqual((plugin / "VERSION").read_text(encoding="utf-8").strip(), VERSION)
            for target in TARGETS:
                name = "vivago-agent.exe" if target.startswith("windows-") else "vivago-agent"
                self.assertTrue((plugin / "bin" / target / name).is_file())

            codex_marketplace = json.loads(
                (marketplace / ".agents" / "plugins" / "marketplace.json").read_text(
                    encoding="utf-8"
                )
            )
            claude_marketplace = json.loads(
                (marketplace / ".claude-plugin" / "marketplace.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(codex_marketplace["name"], "vivago")
            self.assertEqual(codex_marketplace["interface"]["displayName"], "Vivago")
            self.assertEqual(claude_marketplace["name"], "vivago")
            self.assertNotIn("development", json.dumps(claude_marketplace).lower())

            scripts = plugin / "skills" / "vivago-agent-cli" / "scripts"
            self.assertTrue((scripts / "vivago-agent").stat().st_mode & 0o111)
            self.assertTrue((scripts / "vivago-agent.cmd").is_file())
            self.assertTrue((plugin / "SHA256SUMS").is_file())
            for name in ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES.md"):
                self.assertEqual(
                    (plugin / name).read_text(encoding="utf-8"),
                    (REPO_ROOT / name).read_text(encoding="utf-8"),
                )

    def test_assembler_rejects_binary_with_development_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary_root = _write_binaries(root, suffix=" https://dev.vivago.ai")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ASSEMBLER),
                    "--plugin-template",
                    str(REPO_ROOT / "plugin"),
                    "--binary-root",
                    str(binary_root),
                    "--output",
                    str(root / "marketplace"),
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
            self.assertIn("forbidden endpoint", result.stderr)

    def test_verifier_accepts_complete_beta_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marketplace = _assemble(Path(directory))
            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--marketplace",
                    str(marketplace),
                    "--version",
                    VERSION,
                    "--source-revision",
                    REVISION,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"ok":true', result.stdout)

    def test_verifier_rejects_development_marker_even_with_stale_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marketplace = _assemble(Path(directory))
            skill = (
                marketplace
                / "plugins"
                / "vivago-agent-cli"
                / "skills"
                / "vivago-agent-cli"
                / "SKILL.md"
            )
            skill.write_text(
                skill.read_text(encoding="utf-8") + "\nhttps://dev.vivago.ai/agent/login\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--marketplace",
                    str(marketplace),
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
            self.assertIn("forbidden environment marker", result.stderr)


if __name__ == "__main__":
    unittest.main()
