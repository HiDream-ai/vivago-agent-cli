#!/usr/bin/env python3
"""Validate the immutable numeric development release channel."""

from __future__ import annotations

import json
import re
import sys


DEV_RELEASE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-dev\.(0|[1-9]\d*)$"
)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1 or DEV_RELEASE.fullmatch(arguments[0]) is None:
        print("error: development release version must match X.Y.Z-dev.N", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "version": arguments[0]}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
