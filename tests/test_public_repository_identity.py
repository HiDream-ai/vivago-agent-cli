from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPANY_MODULE = "github.com/HiDream-ai/vivago-agent-cli"
PERSONAL_MODULE = "github.com/ChaoXia-Beginer/vivago-agent-cli"


class PublicRepositoryIdentityTests(unittest.TestCase):
    def test_go_module_uses_company_repository_as_canonical_identity(self) -> None:
        first_line = (REPO_ROOT / "go.mod").read_text(encoding="utf-8").splitlines()[0]

        self.assertEqual(first_line, f"module {COMPANY_MODULE}")

    def test_go_source_has_no_personal_repository_imports(self) -> None:
        offenders = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in REPO_ROOT.rglob("*.go")
            if PERSONAL_MODULE in path.read_text(encoding="utf-8")
        ]

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
