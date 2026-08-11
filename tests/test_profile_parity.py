from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProfileParityTests(unittest.TestCase):
    def test_compile_time_profile_can_only_change_environment_identity(self) -> None:
        profile = (REPO_ROOT / "internal" / "config" / "profile.go").read_text(
            encoding="utf-8"
        )
        struct_body = profile.split("type Profile struct {", 1)[1].split("}", 1)[0]
        fields = {
            line.split()[0]
            for line in struct_body.splitlines()
            if line.startswith("\t") and len(line.split()) == 2
        }

        self.assertEqual(fields, {"Name", "APIBaseURL", "WebBaseURL", "LoginURL"})


if __name__ == "__main__":
    unittest.main()
