from __future__ import annotations

import json
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
REVISION = "d" * 40


def _write_binaries(root: Path, version: str, login_url: str) -> Path:
    binary_root = root / "binaries"
    for target in TARGETS:
        target_dir = binary_root / target
        target_dir.mkdir(parents=True)
        name = "vivago-agent.exe" if target.startswith("windows-") else "vivago-agent"
        binary = target_dir / name
        binary.write_bytes(f"fake-{target} {version} {REVISION} {login_url}".encode())
        binary.chmod(0o755)
    return binary_root


def _assemble(
    root: Path, script: str, output_name: str, version: str, login_url: str
) -> Path:
    output = root / f"{output_name}-marketplace"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / script),
            "--plugin-template",
            str(REPO_ROOT / "plugin"),
            "--binary-root",
            str(_write_binaries(root / f"{output_name}-inputs", version, login_url)),
            "--output",
            str(output),
            "--version",
            version,
            "--source-revision",
            REVISION,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return output


def _plugin_files(plugin: Path) -> dict[str, bytes]:
    ignored = {"BUILD_INFO.json", "SHA256SUMS", "VERSION"}
    result: dict[str, bytes] = {}
    for path in plugin.rglob("*"):
        relative = path.relative_to(plugin).as_posix()
        if not path.is_file() or relative in ignored or relative.startswith("bin/"):
            continue
        if relative in {".codex-plugin/plugin.json", ".claude-plugin/plugin.json"}:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["version"] = "<release-version>"
            result[relative] = json.dumps(payload, sort_keys=True).encode()
        else:
            result[relative] = path.read_bytes()
    return result


class DistributionParityTests(unittest.TestCase):
    def test_dev_and_beta_expose_the_same_plugin_except_release_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dev = _assemble(
                root,
                "assemble_go_distribution.py",
                "dev",
                "0.3.0-dev.8",
                "https://dev.vivago.ai/agent/login",
            )
            beta = _assemble(
                root,
                "assemble_beta_distribution.py",
                "beta",
                "0.3.0-beta.1",
                "https://vivago.ai/agent/login",
            )

            self.assertEqual(
                _plugin_files(dev / "plugins" / "vivago-agent-cli"),
                _plugin_files(beta / "plugins" / "vivago-agent-cli"),
            )

            dev_codex = json.loads(
                (dev / ".agents" / "plugins" / "marketplace.json").read_text()
            )
            beta_codex = json.loads(
                (beta / ".agents" / "plugins" / "marketplace.json").read_text()
            )
            dev_codex["name"] = beta_codex["name"]
            self.assertEqual(dev_codex, beta_codex)

            dev_claude = json.loads(
                (dev / ".claude-plugin" / "marketplace.json").read_text()
            )
            beta_claude = json.loads(
                (beta / ".claude-plugin" / "marketplace.json").read_text()
            )
            dev_claude["name"] = beta_claude["name"]
            dev_claude["plugins"][0]["version"] = beta_claude["plugins"][0]["version"]
            self.assertEqual(dev_claude, beta_claude)


if __name__ == "__main__":
    unittest.main()
