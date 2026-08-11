from __future__ import annotations

import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_go_binaries.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_go_binaries", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Go builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GoBuildMatrixTests(unittest.TestCase):
    def test_builder_uses_dev_profile_and_all_six_targets(self) -> None:
        builder = _load_builder()
        calls: list[tuple[list[str], dict[str, str]]] = []

        def fake_run(command, *, cwd, env, check):
            self.assertEqual(Path(cwd), REPO_ROOT)
            self.assertTrue(check)
            calls.append((list(command), dict(env)))
            output = Path(command[command.index("-o") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fake-go-binary https://dev.vivago.ai/agent/login")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "binaries"
            args = argparse.Namespace(
                output=output,
                version="0.3.0-dev.1",
                source_revision="a" * 40,
                go_binary="go",
            )
            with patch.object(builder.subprocess, "run", side_effect=fake_run):
                result = builder.build(args)

            self.assertEqual(result, output)
            self.assertEqual(len(calls), 6)
            targets = {(env["GOOS"], env["GOARCH"]) for _, env in calls}
            self.assertEqual(
                targets,
                {
                    ("darwin", "arm64"),
                    ("darwin", "amd64"),
                    ("linux", "arm64"),
                    ("linux", "amd64"),
                    ("windows", "arm64"),
                    ("windows", "amd64"),
                },
            )
            for command, env in calls:
                self.assertEqual(env["CGO_ENABLED"], "0")
                self.assertIn("-trimpath", command)
                self.assertIn("-buildvcs=false", command)
                ldflags = command[command.index("-ldflags") + 1]
                self.assertIn("main.version=0.3.0-dev.1", ldflags)
                self.assertIn("main.gitSHA=" + "a" * 40, ldflags)
                self.assertIn("main.channel=dev", ldflags)

    def test_builder_rejects_binary_with_production_login_endpoint(self) -> None:
        builder = _load_builder()

        def fake_run(command, *, cwd, env, check):
            output = Path(command[command.index("-o") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(
                b"https://dev.vivago.ai/agent/login https://vivago.ai/agent/login"
            )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "binaries"
            args = argparse.Namespace(
                output=output,
                version="0.3.0-dev.1",
                source_revision="d" * 40,
                go_binary="go",
            )
            with patch.object(builder.subprocess, "run", side_effect=fake_run):
                with self.assertRaisesRegex(ValueError, "forbidden endpoint"):
                    builder.build(args)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
