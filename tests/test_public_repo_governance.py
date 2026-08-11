from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
