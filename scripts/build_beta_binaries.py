#!/usr/bin/env python3
"""Build the six-target Go public Beta binary matrix with the prod profile."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ("darwin", "arm64"),
    ("darwin", "amd64"),
    ("linux", "arm64"),
    ("linux", "amd64"),
    ("windows", "arm64"),
    ("windows", "amd64"),
)
BETA_VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-beta\.([1-9]\d*)$"
)
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
REQUIRED_ENDPOINT = b"https://vivago.ai/agent/login"
FORBIDDEN_ENDPOINTS = (
    b"https://dev.vivago.ai",
    b"domestic-dev",
    b"domestic-prod",
    b"storage-cdn.hidreamai.com",
    b"media.hidreamai.com",
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--go-binary", default="go")
    return parser.parse_args(argv)


def build(args: argparse.Namespace) -> Path:
    if not BETA_VERSION.fullmatch(args.version):
        raise ValueError("beta version must match X.Y.Z-beta.N with N greater than zero")
    if not REVISION.fullmatch(args.source_revision):
        raise ValueError("source revision must be a full 40-character Git SHA")
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")

    source_revision = args.source_revision.lower()
    args.output.mkdir(parents=True)
    ldflags = " ".join(
        (
            "-s",
            "-w",
            f"-X main.version={args.version}",
            f"-X main.gitSHA={source_revision}",
            "-X main.channel=beta",
        )
    )
    try:
        for operating_system, architecture in TARGETS:
            target = f"{operating_system}-{architecture}"
            binary_name = "vivago-agent.exe" if operating_system == "windows" else "vivago-agent"
            output = args.output / target / binary_name
            output.parent.mkdir(parents=True)
            environment = os.environ.copy()
            environment.update(
                {
                    "GOOS": operating_system,
                    "GOARCH": architecture,
                    "CGO_ENABLED": "0",
                }
            )
            subprocess.run(
                [
                    args.go_binary,
                    "build",
                    "-tags",
                    "prod",
                    "-buildvcs=false",
                    "-trimpath",
                    "-ldflags",
                    ldflags,
                    "-o",
                    str(output),
                    "./cmd/vivago-agent",
                ],
                cwd=REPO_ROOT,
                env=environment,
                check=True,
            )
            if not output.is_file():
                raise ValueError(f"Go build did not create target binary: {target}")
            binary_data = output.read_bytes()
            if (
                args.version.encode() not in binary_data
                or source_revision.encode() not in binary_data
                or REQUIRED_ENDPOINT not in binary_data
            ):
                raise ValueError(f"target binary provenance mismatch: {target}")
            if any(marker in binary_data for marker in FORBIDDEN_ENDPOINTS):
                raise ValueError(f"target binary contains a forbidden endpoint: {target}")
            output.chmod(0o755)

        (args.output / "BUILD_MATRIX.json").write_text(
            json.dumps(
                {
                    "version": args.version,
                    "source_revision": source_revision,
                    "channel": "beta",
                    "profile": "prod",
                    "targets": [f"{os_name}-{arch}" for os_name, arch in TARGETS],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(args.output, ignore_errors=True)
        raise
    return args.output


def main(argv: list[str] | None = None) -> int:
    try:
        output = build(_arguments(argv))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "binary_root": str(output)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
