from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_host_plugin_lifecycle.py"
TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_host_plugin_lifecycle", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load host lifecycle verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HostPluginLifecycleVerifierTests(unittest.TestCase):
    def test_supported_cases_are_exactly_six_targets_times_two_hosts(self) -> None:
        verifier = _load_verifier()

        self.assertEqual(verifier.TARGETS, TARGETS)
        self.assertEqual(verifier.HOSTS, ("codex", "claude-code"))
        self.assertEqual(
            verifier.CASES,
            tuple((target, host) for target in TARGETS for host in verifier.HOSTS),
        )

    def test_host_environment_is_isolated_and_disables_claude_updates(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            codex = verifier._host_environment("codex", root)
            claude = verifier._host_environment("claude-code", root)

            self.assertEqual(codex["CODEX_HOME"], str(root / "codex-home"))
            self.assertNotIn("CLAUDE_CONFIG_DIR", codex)
            self.assertEqual(claude["CLAUDE_CONFIG_DIR"], str(root / "claude-home"))
            self.assertEqual(claude["DISABLE_AUTOUPDATER"], "1")
            self.assertNotIn("CODEX_HOME", claude)

    def test_replace_marketplace_removes_stale_files(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "VERSION").write_text("0.3.0-dev.4\n", encoding="utf-8")
            git_objects = source / ".git" / "objects"
            git_objects.mkdir(parents=True)
            (git_objects / "readonly-object").write_text("metadata", encoding="utf-8")
            (destination / "stale.txt").write_text("stale", encoding="utf-8")

            verifier._replace_marketplace(source, destination)

            self.assertEqual(
                (destination / "VERSION").read_text(encoding="utf-8"),
                "0.3.0-dev.4\n",
            )
            self.assertFalse((destination / "stale.txt").exists())
            self.assertFalse((destination / ".git").exists())

    def test_lifecycle_order_is_install_upgrade_rollback_reupgrade(self) -> None:
        verifier = _load_verifier()

        self.assertEqual(
            verifier.PHASES,
            (
                ("install", "previous"),
                ("upgrade", "candidate"),
                ("rollback", "previous"),
                ("reupgrade", "candidate"),
            ),
        )

    def test_windows_launcher_command_preserves_batch_argument_boundaries(self) -> None:
        verifier = _load_verifier()
        launcher = Path(r"C:\Program Files\Vivago Agent\vivago-agent.cmd")

        self.assertEqual(
            verifier._launcher_command(launcher, "windows-arm64", "doctor"),
            [
                "cmd.exe",
                "/d",
                "/c",
                "call",
                str(launcher),
                "--json",
                "doctor",
            ],
        )

    def test_windows_host_command_preserves_npm_shim_argument_boundaries(self) -> None:
        verifier = _load_verifier()
        executable = Path(r"C:\CI\npm\codex.cmd")

        self.assertEqual(
            verifier._host_command(executable, "windows-amd64", ["plugin", "list", "--json"]),
            [
                "cmd.exe",
                "/d",
                "/c",
                "call",
                str(executable),
                "plugin",
                "list",
                "--json",
            ],
        )


if __name__ == "__main__":
    unittest.main()
