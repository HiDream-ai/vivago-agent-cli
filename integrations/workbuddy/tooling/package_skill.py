#!/usr/bin/env python3
"""Build a deterministic WorkBuddy Skill ZIP with a single skill root."""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

from validate_skill import validate


ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def package(skill_root: Path, output: Path) -> str:
    skill_root = skill_root.resolve()
    files = validate(skill_root)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for source in sorted(files, key=lambda item: item.relative_to(skill_root).as_posix()):
                relative = source.relative_to(skill_root).as_posix()
                info = zipfile.ZipInfo(f"{skill_root.name}/{relative}", ZIP_TIMESTAMP)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, source.read_bytes(), compresslevel=9)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = package(args.skill, args.output)
    print(f"WorkBuddy skill package created: {args.output} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
