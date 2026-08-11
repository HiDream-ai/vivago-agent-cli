from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_beta_host_plugin_lifecycle.py"
TARGETS = (
    "darwin-arm64",
    "darwin-amd64",
    "linux-arm64",
    "linux-amd64",
    "windows-arm64",
    "windows-amd64",
)


def _load_verifier():
    scripts = str(REPO_ROOT / "scripts")
    sys.path.insert(0, scripts)
    try:
        spec = importlib.util.spec_from_file_location(
            "verify_beta_host_plugin_lifecycle",
            SCRIPT_PATH,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load Beta host lifecycle verifier")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(scripts)


def _marketplace(root: Path, *, version: str, channel: str, profile: str) -> Path:
    plugin = root / "plugins" / "vivago-agent-cli"
    plugin.mkdir(parents=True)
    (plugin / "VERSION").write_text(version + "\n", encoding="utf-8")
    (plugin / "BUILD_INFO.json").write_text(
        json.dumps(
            {
                "version": version,
                "source_revision": "a" * 40,
                "channel": channel,
                "profile": profile,
                "targets": list(TARGETS),
            }
        ),
        encoding="utf-8",
    )
    for relative in (
        Path(".agents/plugins/marketplace.json"),
        Path(".claude-plugin/marketplace.json"),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"name": "vivago"}), encoding="utf-8")
    return root


class BetaHostPluginLifecycleVerifierTests(unittest.TestCase):
    def test_policy_is_fixed_to_public_beta_identity_and_production(self) -> None:
        verifier = _load_verifier()

        self.assertEqual(verifier.POLICY.channel, "beta")
        self.assertEqual(verifier.POLICY.profile, "prod")
        self.assertEqual(verifier.POLICY.environment, "overseas-production")
        self.assertEqual(verifier.POLICY.plugin_id, "vivago-agent-cli@vivago")
        self.assertEqual(verifier.POLICY.marketplace_name, "vivago")

    def test_accepts_only_beta_marketplace_metadata(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            marketplace = _marketplace(
                Path(directory) / "marketplace",
                version="0.3.0-beta.1",
                channel="beta",
                profile="prod",
            )

            info = verifier._build_info(marketplace, verifier.POLICY)

        self.assertEqual(info["version"], "0.3.0-beta.1")

    def test_rejects_dev_marketplace_metadata(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            marketplace = _marketplace(
                Path(directory) / "marketplace",
                version="0.3.0-dev.9",
                channel="dev",
                profile="dev",
            )

            with self.assertRaisesRegex(ValueError, "invalid channel"):
                verifier._build_info(marketplace, verifier.POLICY)

    def test_rejects_non_beta_version_even_with_production_metadata(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory() as directory:
            marketplace = _marketplace(
                Path(directory) / "marketplace",
                version="0.3.0",
                channel="beta",
                profile="prod",
            )

            with self.assertRaisesRegex(ValueError, "invalid version"):
                verifier._build_info(marketplace, verifier.POLICY)


if __name__ == "__main__":
    unittest.main()
