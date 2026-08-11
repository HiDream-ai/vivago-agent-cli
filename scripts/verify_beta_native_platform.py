#!/usr/bin/env python3
"""Verify one production Beta plugin on its native GitHub runner."""

from __future__ import annotations

import re

from verify_native_platform import main_for_policy


BETA_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-beta\.([1-9]\d*)$"
)


def main(argv: list[str] | None = None) -> int:
    return main_for_policy(
        argv,
        expected_channel="beta",
        expected_profile="prod",
        expected_environment="overseas-production",
        expected_version=BETA_VERSION,
        version_error="beta version must match X.Y.Z-beta.N with N greater than zero",
        environment_error="doctor environment is not the overseas production profile",
    )


if __name__ == "__main__":
    raise SystemExit(main())
