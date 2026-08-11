from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_TEMPLATE = REPO_ROOT / "plugin"
TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)


class GoDistributionTests(unittest.TestCase):
    def test_assembler_creates_six_platform_dev_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary_root = root / "binaries"
            for target in TARGETS:
                target_dir = binary_root / target
                target_dir.mkdir(parents=True)
                binary_name = "vivago-agent.exe" if target.startswith("windows-") else "vivago-agent"
                binary = target_dir / binary_name
                binary.write_bytes(
                    (
                        f"fake-{target} 0.3.0-dev.1 {'a' * 40} "
                        "https://dev.vivago.ai/agent/login"
                    ).encode()
                )
                binary.chmod(0o755)
            output = root / "marketplace"

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "assemble_go_distribution.py"),
                    "--plugin-template",
                    str(PLUGIN_TEMPLATE),
                    "--binary-root",
                    str(binary_root),
                    "--output",
                    str(output),
                    "--version",
                    "0.3.0-dev.1",
                    "--source-revision",
                    "a" * 40,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            plugin = output / "plugins" / "vivago-agent-cli"
            self.assertFalse(any(plugin.rglob(".DS_Store")))
            for target in TARGETS:
                binary_name = "vivago-agent.exe" if target.startswith("windows-") else "vivago-agent"
                bundled = plugin / "bin" / target / binary_name
                self.assertIn(f"fake-{target}".encode(), bundled.read_bytes())
                if not target.startswith("windows-"):
                    self.assertTrue(bundled.stat().st_mode & 0o111)

            scripts = plugin / "skills" / "vivago-agent-cli" / "scripts"
            posix_launcher = (scripts / "vivago-agent").read_text(encoding="utf-8")
            windows_launcher = (scripts / "vivago-agent.cmd").read_text(encoding="utf-8")
            for value in ("Darwin", "Linux", "MINGW", "arm64", "aarch64", "x86_64"):
                self.assertIn(value, posix_launcher)
            self.assertIn("windows-arm64", windows_launcher)
            self.assertIn("windows-amd64", windows_launcher)
            self.assertNotIn("vivago-client", posix_launcher + windows_launcher)
            self.assertNotIn("curl", posix_launcher + windows_launcher)

            codex_manifest = json.loads(
                (plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
            )
            claude_manifest = json.loads(
                (plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
            )
            source_claude_manifest = json.loads(
                (PLUGIN_TEMPLATE / ".claude-plugin" / "plugin.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(codex_manifest["version"], "0.3.0-dev.1")
            self.assertEqual(
                codex_manifest["interface"]["displayName"],
                "Vivago Agent CLI",
            )
            self.assertEqual(claude_manifest["version"], "0.3.0-dev.1")
            self.assertEqual(
                {key: value for key, value in claude_manifest.items() if key != "version"},
                {
                    key: value
                    for key, value in source_claude_manifest.items()
                    if key != "version"
                },
            )
            assets = plugin / "assets"
            for name in (
                "vivago-agent-logo.svg",
                "vivago-agent-logo.png",
                "vivago-agent-logo-dark.svg",
                "vivago-agent-logo-dark.png",
                "vivago-agent-icon.svg",
                "vivago-agent-icon.png",
            ):
                self.assertTrue((assets / name).is_file(), name)

            build_info = json.loads((plugin / "BUILD_INFO.json").read_text(encoding="utf-8"))
            self.assertEqual(build_info["profile"], "dev")
            self.assertEqual(build_info["channel"], "dev")
            self.assertEqual(build_info["source_revision"], "a" * 40)
            self.assertEqual(build_info["targets"], list(TARGETS))
            for name in ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES.md"):
                self.assertEqual(
                    (plugin / name).read_text(encoding="utf-8"),
                    (REPO_ROOT / name).read_text(encoding="utf-8"),
                )
            checksums = (plugin / "SHA256SUMS").read_text(encoding="utf-8")
            for target in TARGETS:
                self.assertIn(f"bin/{target}/vivago-agent", checksums)

            codex_marketplace = json.loads(
                (output / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
            )
            claude_marketplace = json.loads(
                (output / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
            )
            self.assertEqual(codex_marketplace["name"], "vivago-dev")
            self.assertEqual(
                codex_marketplace["interface"]["displayName"],
                "Vivago Agent CLI",
            )
            self.assertEqual(codex_marketplace["plugins"][0]["policy"]["authentication"], "ON_USE")
            self.assertEqual(claude_marketplace["name"], "vivago-dev")
            self.assertEqual(
                codex_marketplace["plugins"][0]["source"]["path"],
                "./plugins/vivago-agent-cli",
            )

    def test_assembler_rejects_missing_platform_binary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary_root = root / "binaries"
            binary_root.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "assemble_go_distribution.py"),
                    "--plugin-template",
                    str(PLUGIN_TEMPLATE),
                    "--binary-root",
                    str(binary_root),
                    "--output",
                    str(root / "marketplace"),
                    "--version",
                    "0.3.0-dev.1",
                    "--source-revision",
                    "b" * 40,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing target binary", result.stderr)

    def test_posix_launcher_selects_current_bundled_target(self) -> None:
        system = platform.system().lower()
        machine = platform.machine().lower()
        if system not in {"darwin", "linux"}:
            self.skipTest("POSIX launcher test requires macOS or Linux")
        architecture = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
        expected_target = f"{system}-{architecture}"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary_root = root / "binaries"
            for target in TARGETS:
                target_dir = binary_root / target
                target_dir.mkdir(parents=True)
                binary_name = "vivago-agent.exe" if target.startswith("windows-") else "vivago-agent"
                binary = target_dir / binary_name
                if target.startswith("windows-"):
                    binary.write_bytes(
                        (
                            f"fake-windows 0.3.0-dev.1 {'c' * 40} "
                            "https://dev.vivago.ai/agent/login"
                        ).encode()
                    )
                else:
                    binary.write_text(
                        f"#!/bin/sh\n# 0.3.0-dev.1 {'c' * 40} "
                        "https://dev.vivago.ai/agent/login\n"
                        f"printf '%s\\n' '{target}'\n",
                        encoding="utf-8",
                    )
                binary.chmod(0o755)
            output = root / "marketplace"
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "assemble_go_distribution.py"),
                    "--plugin-template",
                    str(PLUGIN_TEMPLATE),
                    "--binary-root",
                    str(binary_root),
                    "--output",
                    str(output),
                    "--version",
                    "0.3.0-dev.1",
                    "--source-revision",
                    "c" * 40,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            launcher = (
                output
                / "plugins"
                / "vivago-agent-cli"
                / "skills"
                / "vivago-agent-cli"
                / "scripts"
                / "vivago-agent"
            )
            launched = subprocess.run(
                [str(launcher), "--json", "version"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(launched.returncode, 0, launched.stderr)
            self.assertEqual(launched.stdout.strip(), expected_target)

    def test_assembler_rejects_binary_provenance_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary_root = root / "binaries"
            for target in TARGETS:
                target_dir = binary_root / target
                target_dir.mkdir(parents=True)
                name = "vivago-agent.exe" if target.startswith("windows-") else "vivago-agent"
                binary = target_dir / name
                binary.write_bytes(
                    b"0.3.0-dev.1 " + b"e" * 40 + b" https://dev.vivago.ai/agent/login"
                )
                binary.chmod(0o755)
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "assemble_go_distribution.py"),
                    "--plugin-template",
                    str(PLUGIN_TEMPLATE),
                    "--binary-root",
                    str(binary_root),
                    "--output",
                    str(root / "marketplace"),
                    "--version",
                    "0.3.0-dev.1",
                    "--source-revision",
                    "f" * 40,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("provenance mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
