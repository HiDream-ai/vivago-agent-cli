from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKBUDDY_ROOT = ROOT / "integrations" / "workbuddy"
SKILL_ROOT = WORKBUDDY_ROOT / "gouda-agent"
VALIDATOR = WORKBUDDY_ROOT / "tooling" / "validate_skill.py"
PACKAGER = WORKBUDDY_ROOT / "tooling" / "package_skill.py"


class WorkBuddySkillTests(unittest.TestCase):
    def test_domestic_skill_keeps_the_cli_operational_reference_structure(self) -> None:
        expected = {
            "brief-guide.md",
            "capability-limits.md",
            "delivery-playbook.md",
            "output-shapes.md",
            "recovery-runbook.md",
        }
        references = SKILL_ROOT / "references"
        names = {item.name for item in references.iterdir() if item.is_file()}
        self.assertTrue(expected <= names, f"missing operational references: {sorted(expected - names)}")
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for name in expected:
            self.assertIn(f"@references/{name}", skill_text)
        self.assertFalse((SKILL_ROOT / "agents").exists())

    def test_marketplace_package_contains_only_domestic_product_language(self) -> None:
        forbidden = ("海外", "overseas", "vivago.ai", "google_key")
        violations: list[str] = []
        for item in SKILL_ROOT.rglob("*"):
            if not item.is_file():
                continue
            text = item.read_text(encoding="utf-8")
            for marker in forbidden:
                if marker.lower() in text.lower():
                    violations.append(f"{item.relative_to(SKILL_ROOT)}: {marker}")
        self.assertEqual(violations, [])

    def test_skill_markdown_is_public_facing_and_has_no_broken_assets(self) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("![img.png](img.png)", skill_text)
        for heading in (
            "## 能力介绍",
            "## 适合处理的任务",
            "## 使用方法",
            "## 任务执行与交付",
            "## 继续修改与恢复",
            "## 安全与隐私",
            "## Agent 执行规范",
        ):
            self.assertIn(heading, skill_text)
        self.assertIn("node scripts/gouda-agent.js doctor", skill_text)
        self.assertNotIn("内部的 MCP 工具和 Skill", skill_text)

    def test_skill_and_runtime_versions_are_1_0_1_for_payment_redirect_release(self) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        config_text = (SKILL_ROOT / "scripts" / "config.js").read_text(encoding="utf-8")
        self.assertIn("version: 1.0.1", skill_text)
        self.assertIn('skillVersion: "1.0.1"', config_text)

    def test_skill_passes_repository_validator(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(SKILL_ROOT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WorkBuddy skill validation passed", result.stdout)

    def test_packaging_is_deterministic_and_contains_only_skill_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.zip"
            second = Path(temporary) / "second.zip"
            for output in (first, second):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(PACKAGER),
                        "--skill",
                        str(SKILL_ROOT),
                        "--output",
                        str(output),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            self.assertEqual(
                hashlib.sha256(first.read_bytes()).digest(),
                hashlib.sha256(second.read_bytes()).digest(),
            )
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
            self.assertIn("gouda-agent/SKILL.md", names)
            self.assertIn("gouda-agent/scripts/gouda-agent.js", names)
            self.assertTrue(all(name.startswith("gouda-agent/") for name in names))
            self.assertTrue(
                all(len(Path(name).parts) <= 3 for name in names),
                "WorkBuddy packages support only skill-root/second-level/file",
            )
            self.assertFalse(any("tests/" in name or "tooling/" in name for name in names))
            self.assertFalse(any(name.endswith((".exe", ".dll", ".so", ".dylib")) for name in names))


if __name__ == "__main__":
    unittest.main()
