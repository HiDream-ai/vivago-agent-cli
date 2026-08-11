#!/usr/bin/env python3
"""Verify production Beta plugin lifecycle in an isolated Codex or Claude Code host."""

from __future__ import annotations

import re

from verify_host_plugin_lifecycle import HostPolicy, _build_info, main_for_policy


BETA_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-beta\.([1-9]\d*)$"
)
POLICY = HostPolicy(
    channel="beta",
    profile="prod",
    environment="overseas-production",
    plugin_id="vivago-agent-cli@vivago",
    marketplace_name="vivago",
    version_pattern=BETA_VERSION,
)


def main(argv: list[str] | None = None) -> int:
    return main_for_policy(argv, POLICY)


if __name__ == "__main__":
    raise SystemExit(main())
