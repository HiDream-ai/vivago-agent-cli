from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PublicRepositoryGovernanceTests(unittest.TestCase):
    def test_public_source_has_no_user_specific_absolute_paths(self) -> None:
        forbidden = ("/" + "Users" + "/", "C:" + "\\" + "Users" + "\\")
        matches: list[str] = []
        for path in REPO_ROOT.rglob("*"):
            if (
                not path.is_file()
                or ".git" in path.parts
                or ".idea" in path.parts
                or "build" in path.parts
                or "__pycache__" in path.parts
                or ".venv" in path.parts
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(marker in text for marker in forbidden):
                matches.append(path.relative_to(REPO_ROOT).as_posix())

        self.assertEqual(matches, [])

    def test_repository_and_plugin_ship_standard_apache_license(self) -> None:
        repository_license = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")

        self.assertIn("Apache License\n                           Version 2.0, January 2004", repository_license)
        self.assertIn("END OF TERMS AND CONDITIONS", repository_license)
        for relative in (
            "plugin/.codex-plugin/plugin.json",
            "plugin/.claude-plugin/plugin.json",
        ):
            manifest = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))
            self.assertEqual(manifest["license"], "Apache-2.0", relative)

    def test_notice_is_packaged_and_has_no_legal_placeholder(self) -> None:
        notice = (REPO_ROOT / "NOTICE").read_text(encoding="utf-8")

        self.assertIn("VivagoAgent CLI", notice)
        self.assertIn("HiDream.ai contributors", notice)
        self.assertNotIn("[", notice)

    def test_third_party_notices_cover_distributed_dependencies(self) -> None:
        notices = (REPO_ROOT / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")

        for dependency in (
            "github.com/gofrs/flock",
            "github.com/zalando/go-keyring",
            "github.com/danieljoos/wincred",
            "github.com/godbus/dbus/v5",
            "golang.org/x/sys",
            "PyYAML",
            "shellescape",
        ):
            self.assertIn(dependency, notices)
        for license_name in ("BSD-2-Clause", "BSD-3-Clause", "MIT"):
            self.assertIn(license_name, notices)

    def test_security_policy_and_codeowners_have_actionable_company_defaults(self) -> None:
        security = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
        codeowners = (REPO_ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")

        self.assertIn("https://github.com/HiDream-ai/vivago-agent-cli/security/advisories/new", security)
        self.assertIn("public Beta", security)
        self.assertNotIn("example.com", security)
        self.assertEqual(codeowners.strip(), "* @ChaoXia-Beginer")

    def test_public_install_docs_lead_with_company_beta_channel(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_zh = (REPO_ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        install_guide = (
            REPO_ROOT / "docs" / "vivago-agent-plugin-product-install-guide.md"
        ).read_text(encoding="utf-8")
        company_repository = "https://github.com/HiDream-ai/vivago-agent-cli.git"

        self.assertIn("## Install the public Beta", readme)
        self.assertIn("## 安装公开 Beta", readme_zh)
        for document in (readme, readme_zh, install_guide):
            self.assertIn(company_repository, document)
            self.assertIn("vivago-agent-cli@vivago", document)
            self.assertIn("marketplace upgrade vivago", document)
            self.assertIn("marketplace update vivago", document)
        for document in (readme, readme_zh, install_guide):
            self.assertNotIn("ChaoXia-Beginer/vivago-agent-cli", document)
            self.assertNotIn("vivago-agent-cli@vivago-dev", document)
            self.assertNotIn("## 维护者：安装 Dev 包", document)
        self.assertIn("codex plugin remove vivago-agent-cli@vivago", install_guide)
        self.assertIn("claude plugin uninstall vivago-agent-cli@vivago", install_guide)


if __name__ == "__main__":
    unittest.main()
