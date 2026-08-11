from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugin"
ASSET_ROOT = PLUGIN_ROOT / "assets"


def png_metadata(path: Path) -> tuple[int, int, set[bytes]]:
    payload = path.read_bytes()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"{path.name} is not a PNG")
    width, height = struct.unpack(">II", payload[16:24])
    chunks: set[bytes] = set()
    offset = 8
    while offset + 12 <= len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        kind = payload[offset + 4 : offset + 8]
        chunks.add(kind)
        offset += 12 + length
        if kind == b"IEND":
            break
    return width, height, chunks


class PluginBrandAssetTests(unittest.TestCase):
    def test_codex_manifest_references_packaged_brand_assets(self) -> None:
        manifest = json.loads(
            (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        interface = manifest["interface"]
        self.assertEqual(interface["displayName"], "Vivago Agent CLI")
        self.assertEqual(interface["brandColor"], "#574DFF")
        self.assertEqual(
            interface["composerIcon"],
            "./assets/vivago-agent-icon.png",
        )
        self.assertEqual(
            interface["logo"],
            "./assets/vivago-agent-logo.svg",
        )
        self.assertEqual(
            interface["logoDark"],
            "./assets/vivago-agent-logo-dark.svg",
        )

    def test_skill_metadata_does_not_duplicate_plugin_brand_assets(self) -> None:
        metadata = (
            PLUGIN_ROOT / "skills" / "vivago-agent-cli" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("icon_small:", metadata)
        self.assertNotIn("icon_large:", metadata)
        self.assertIn('brand_color: "#574DFF"', metadata)
        self.assertIn('display_name: "Vivago Agent CLI"', metadata)

    def test_supplied_backgrounds_and_sizes_are_preserved(self) -> None:
        expected = {
            "vivago-agent-logo": (512, "white"),
            "vivago-agent-logo-dark": (512, "black"),
            "vivago-agent-icon": (128, "black"),
        }
        for name, (size, background) in expected.items():
            with self.subTest(asset=name):
                svg = (ASSET_ROOT / f"{name}.svg").read_text(encoding="utf-8")
                self.assertIn(f'width="{size}" height="{size}"', svg)
                self.assertIn(f'<rect width="{size}" height="{size}" fill="{background}"/>', svg)
                width, height, chunks = png_metadata(ASSET_ROOT / f"{name}.png")
                self.assertEqual((width, height), (size, size))
                self.assertTrue({b"sRGB", b"iCCP"} & chunks, "PNG must declare sRGB color")


if __name__ == "__main__":
    unittest.main()
