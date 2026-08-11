from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "generate_spdx_sbom.py"
VERSION = "0.3.0-beta.1"
REVISION = "c" * 40


class SPDXSBOMTests(unittest.TestCase):
    def test_generates_spdx_for_distribution_go_and_python_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marketplace = root / "marketplace"
            binary = marketplace / "plugins" / "vivago-agent-cli" / "bin" / "linux-amd64" / "vivago-agent"
            manifest = marketplace / ".agents" / "plugins" / "marketplace.json"
            binary.parent.mkdir(parents=True)
            manifest.parent.mkdir(parents=True)
            binary.write_bytes(b"binary")
            manifest.write_text('{"name":"vivago"}\n', encoding="utf-8")
            go_mod = root / "go.mod"
            go_mod.write_text(
                "module github.com/HiDream-ai/vivago-agent-cli\n\n"
                "go 1.25\n\n"
                "require (\n"
                "  github.com/gofrs/flock v0.13.0\n"
                "  golang.org/x/sys v0.37.0 // indirect\n"
                ")\n",
                encoding="utf-8",
            )
            requirements = root / "requirements-dev.txt"
            requirements.write_text("PyYAML==6.0.3\n", encoding="utf-8")
            output = marketplace / "SBOM.spdx.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--marketplace",
                    str(marketplace),
                    "--go-mod",
                    str(go_mod),
                    "--requirements",
                    str(requirements),
                    "--version",
                    VERSION,
                    "--source-revision",
                    REVISION,
                    "--created",
                    "2026-08-11T00:00:00Z",
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(document["spdxVersion"], "SPDX-2.3")
        self.assertEqual(document["dataLicense"], "CC0-1.0")
        self.assertEqual(document["creationInfo"]["created"], "2026-08-11T00:00:00Z")
        packages = {(item["name"], item["versionInfo"]) for item in document["packages"]}
        self.assertIn(("github.com/HiDream-ai/vivago-agent-cli", VERSION), packages)
        self.assertIn(("github.com/gofrs/flock", "v0.13.0"), packages)
        self.assertIn(("golang.org/x/sys", "v0.37.0"), packages)
        self.assertIn(("PyYAML", "6.0.3"), packages)
        files = {item["fileName"]: item for item in document["files"]}
        self.assertEqual(
            files["./plugins/vivago-agent-cli/bin/linux-amd64/vivago-agent"]["checksums"],
            [{"algorithm": "SHA256", "checksumValue": hashlib.sha256(b"binary").hexdigest()}],
        )
        self.assertIn("./.agents/plugins/marketplace.json", files)
        self.assertTrue(any(item["relationshipType"] == "DEPENDS_ON" for item in document["relationships"]))
        self.assertTrue(any(item["relationshipType"] == "CONTAINS" for item in document["relationships"]))

    def test_rejects_non_beta_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marketplace = root / "marketplace"
            marketplace.mkdir()
            go_mod = root / "go.mod"
            go_mod.write_text("module example.com/test\n", encoding="utf-8")
            requirements = root / "requirements.txt"
            requirements.write_text("", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--marketplace",
                    str(marketplace),
                    "--go-mod",
                    str(go_mod),
                    "--requirements",
                    str(requirements),
                    "--version",
                    "0.3.0-dev.1",
                    "--source-revision",
                    REVISION,
                    "--created",
                    "2026-08-11T00:00:00Z",
                    "--output",
                    str(root / "SBOM.spdx.json"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("X.Y.Z-beta.N", result.stderr)


if __name__ == "__main__":
    unittest.main()
