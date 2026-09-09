#!/usr/bin/env python3
"""Validate the standalone WorkBuddy Skill package with Python's standard library."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REQUIRED_FRONTMATTER = {
    "name",
    "display_name",
    "display_name_en",
    "description",
    "description_zh",
    "description_en",
    "category",
    "version",
    "author",
}
ALLOWED_TOP_LEVEL = {"SKILL.md", "references", "scripts", "templates"}
ALLOWED_SUFFIXES = {".md", ".js"}
NATIVE_SUFFIXES = {".exe", ".dll", ".so", ".dylib", ".a", ".o"}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_PACKAGE_BYTES = 10 * 1024 * 1024


class ValidationError(ValueError):
    pass


def parse_frontmatter(skill_file: Path) -> dict[str, str]:
    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValidationError("SKILL.md must start with YAML frontmatter")
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as error:
        raise ValidationError("SKILL.md frontmatter is not closed") from error
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    missing = sorted(field for field in REQUIRED_FRONTMATTER if not fields.get(field))
    if missing:
        raise ValidationError(f"SKILL.md is missing required fields: {', '.join(missing)}")
    return fields


def validate(skill_root: Path) -> list[Path]:
    skill_root = skill_root.resolve()
    if not skill_root.is_dir():
        raise ValidationError(f"skill directory does not exist: {skill_root}")
    if skill_root.name != "gouda-agent":
        raise ValidationError("domestic WorkBuddy skill directory must be named gouda-agent")
    skill_file = skill_root / "SKILL.md"
    if not skill_file.is_file():
        raise ValidationError("SKILL.md is required")
    frontmatter = parse_frontmatter(skill_file)
    if frontmatter["name"] != skill_root.name:
        raise ValidationError("SKILL.md name must match its directory")
    if not re.fullmatch(r"\d+\.\d+\.\d+", frontmatter["version"]):
        raise ValidationError("SKILL.md version must use x.y.z format")

    unexpected = sorted(item.name for item in skill_root.iterdir() if item.name not in ALLOWED_TOP_LEVEL)
    if unexpected:
        raise ValidationError(f"unexpected top-level package entries: {', '.join(unexpected)}")

    files: list[Path] = []
    total_size = 0
    for item in sorted(skill_root.rglob("*")):
        if item.is_symlink():
            raise ValidationError(f"symbolic links are forbidden: {item.relative_to(skill_root)}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValidationError(f"non-regular package entry: {item.relative_to(skill_root)}")
        relative = item.relative_to(skill_root)
        if len(relative.parts) > 2:
            raise ValidationError(
                f"directory depth exceeds WorkBuddy limit: {relative}"
            )
        if item.suffix.lower() in NATIVE_SUFFIXES:
            raise ValidationError(f"native binary is forbidden: {relative}")
        if item.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValidationError(f"unsupported file type: {relative}")
        size = item.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValidationError(f"file exceeds size limit: {relative}")
        total_size += size
        try:
            content = item.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValidationError(f"file must be UTF-8 text: {relative}") from error
        if "-----BEGIN PRIVATE KEY-----" in content or "-----BEGIN RSA PRIVATE KEY-----" in content:
            raise ValidationError(f"private key marker found: {relative}")
        if item.suffix == ".js":
            if "vivago.ai" in content or "dev.goudaai.com" in content or "google_key" in content:
                raise ValidationError(f"domestic runtime contains an alternate environment: {relative}")
            checked = subprocess.run(
                ["node", "--check", str(item)],
                capture_output=True,
                text=True,
                check=False,
            )
            if checked.returncode != 0:
                raise ValidationError(f"JavaScript syntax check failed for {relative}: {checked.stderr.strip()}")
        files.append(item)
    if total_size > MAX_PACKAGE_BYTES:
        raise ValidationError("skill package exceeds total size limit")

    skill_text = skill_file.read_text(encoding="utf-8")
    for reference in re.findall(r"@references/([A-Za-z0-9._-]+)", skill_text):
        if not (skill_root / "references" / reference).is_file():
            raise ValidationError(f"referenced file does not exist: references/{reference}")

    config_text = (skill_root / "scripts" / "config.js").read_text(encoding="utf-8")
    required_contracts = {
        'apiBaseURL: "https://goudaai.com"',
        'loginURL: "https://goudaai.com/login"',
        'projectVersion: "v3"',
        'ossCredentialPath: "/prod-api/user/oss_key"',
        'imagePrefix: "https://storage-cdn.hidreamai.com/image/"',
        'mediaPrefix: "https://media-cdn.hidreamai.com/"',
    }
    missing_contracts = sorted(value for value in required_contracts if value not in config_text)
    if missing_contracts:
        raise ValidationError(f"domestic profile contract is incomplete: {missing_contracts}")
    return files


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: validate_skill.py <skill-directory>", file=sys.stderr)
        return 2
    try:
        files = validate(Path(argv[0]))
    except (OSError, ValidationError) as error:
        print(f"WorkBuddy skill validation failed: {error}", file=sys.stderr)
        return 1
    print(f"WorkBuddy skill validation passed: {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
