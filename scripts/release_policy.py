#!/usr/bin/env python3
"""Repository-bound release policy shared by fixed Dev and Beta entrypoints."""

from __future__ import annotations

import re


REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
DEV_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-dev\.([1-9]\d*)$")
BETA_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-beta\.([1-9]\d*)$"
)
DEV_REPOSITORY = "ChaoXia-Beginer/vivago-agent-cli"
BETA_REPOSITORY = "HiDream-ai/vivago-agent-cli"
BETA_REF = "refs/heads/main"


def validate_dev(version: str, repository: str, ref: str, source_revision: str) -> None:
    if not DEV_VERSION.fullmatch(version):
        raise ValueError("development version must match X.Y.Z-dev.N with N greater than zero")
    if repository != DEV_REPOSITORY:
        raise ValueError(f"development repository must be {DEV_REPOSITORY}")
    if not ref.startswith("refs/heads/"):
        raise ValueError("development release ref must be a branch under refs/heads/")
    _validate_revision(source_revision)


def validate_beta(version: str, repository: str, ref: str, source_revision: str) -> None:
    if not BETA_VERSION.fullmatch(version):
        raise ValueError("beta version must match X.Y.Z-beta.N with N greater than zero")
    if repository != BETA_REPOSITORY:
        raise ValueError(f"company repository must be {BETA_REPOSITORY}")
    if ref != BETA_REF:
        raise ValueError(f"beta release ref must be {BETA_REF}")
    _validate_revision(source_revision)


def _validate_revision(source_revision: str) -> None:
    if not REVISION.fullmatch(source_revision):
        raise ValueError("source revision must be a full 40-character Git SHA")
