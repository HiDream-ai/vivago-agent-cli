#!/usr/bin/env python3
"""Publish a parentless Marketplace snapshot with an exact Git lease."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


VERSION = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-(dev|beta)\.([1-9]\d*)$"
)
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")
BUILD_INFO = "plugins/vivago-agent-cli/BUILD_INFO.json"


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace", type=Path, required=True)
    parser.add_argument("--remote", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--channel", choices=("dev", "beta"), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--expected-old-revision")
    return parser.parse_args(argv)


def _run(
    args: list[str], *, cwd: Path | None = None, label: str
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ValueError(f"Git operation failed during {label}")
    return result


def _caller_repository() -> Path:
    result = _run(
        ["git", "rev-parse", "--show-toplevel"],
        label="caller repository discovery",
    )
    return Path(result.stdout.strip()).resolve()


def _remote_revision(repository: Path, remote: str, branch: str) -> str:
    result = _run(
        ["git", "ls-remote", "--heads", remote, f"refs/heads/{branch}"],
        cwd=repository,
        label="remote revision lookup",
    )
    line = result.stdout.strip()
    if not line:
        return ""
    revision, separator, reference = line.partition("\t")
    if separator != "\t" or reference != f"refs/heads/{branch}":
        raise ValueError("Git remote returned an unexpected branch reference")
    return revision


def _version(value: str, channel: str) -> tuple[int, int, int, int]:
    match = VERSION.fullmatch(value)
    if match is None or match.group(4) != channel:
        raise ValueError(f"version must match X.Y.Z-{channel}.N with N greater than zero")
    return tuple(int(match.group(index)) for index in (1, 2, 3, 5))


def _validate_candidate(args: argparse.Namespace, marketplace: Path) -> None:
    if not REVISION.fullmatch(args.source_revision):
        raise ValueError("source revision must be a full 40-character Git SHA")
    path = marketplace / BUILD_INFO
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("candidate BUILD_INFO.json must be an object")
    expected = {
        "version": args.version,
        "source_revision": args.source_revision.lower(),
        "channel": args.channel,
        "profile": "prod" if args.channel == "beta" else "dev",
    }
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise ValueError("candidate BUILD_INFO.json does not match publish arguments")


def _existing_snapshot(
    repository: Path,
    *,
    remote: str,
    branch: str,
    expected_revision: str,
) -> tuple[dict[str, object], str] | None:
    if not expected_revision:
        return None
    _run(
        [
            "git",
            "fetch",
            "--quiet",
            "--depth=1",
            remote,
            f"refs/heads/{branch}",
        ],
        cwd=repository,
        label="existing snapshot fetch",
    )
    fetched = _run(
        ["git", "rev-parse", "FETCH_HEAD"],
        cwd=repository,
        label="existing snapshot revision verification",
    ).stdout.strip()
    if fetched != expected_revision:
        raise ValueError("Marketplace branch changed before validation")
    raw = _run(
        ["git", "show", f"FETCH_HEAD:{BUILD_INFO}"],
        cwd=repository,
        label="existing snapshot metadata read",
    ).stdout
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("existing BUILD_INFO.json must be an object")
    tree = _run(
        ["git", "rev-parse", "FETCH_HEAD^{tree}"],
        cwd=repository,
        label="existing snapshot tree read",
    ).stdout.strip()
    return value, tree


def publish(args: argparse.Namespace) -> dict[str, str | bool]:
    marketplace = args.marketplace.resolve()
    if not marketplace.is_dir():
        raise ValueError("Marketplace directory does not exist")
    candidate_version = _version(args.version, args.channel)
    _validate_candidate(args, marketplace)
    caller_repository = _caller_repository()
    expected_old_revision = _remote_revision(
        caller_repository, args.remote, args.branch
    )
    if (
        args.expected_old_revision is not None
        and args.expected_old_revision != expected_old_revision
    ):
        raise ValueError("Marketplace branch changed since the expected revision")

    with tempfile.TemporaryDirectory() as directory:
        repository = Path(directory) / "snapshot"
        repository.mkdir()
        _run(
            ["git", "init", "--quiet"],
            cwd=repository,
            label="snapshot repository initialization",
        )
        existing_snapshot = _existing_snapshot(
            caller_repository,
            remote=args.remote,
            branch=args.branch,
            expected_revision=expected_old_revision,
        )
        existing = existing_snapshot[0] if existing_snapshot is not None else None
        existing_tree = (
            existing_snapshot[1] if existing_snapshot is not None else None
        )
        same_version = False
        if existing is not None:
            existing_version = existing.get("version")
            if not isinstance(existing_version, str):
                raise ValueError("existing Marketplace version is missing")
            existing_version_key = _version(existing_version, args.channel)
            if existing_version_key > candidate_version:
                raise ValueError("existing Marketplace contains a newer version")
            same_version = existing_version_key == candidate_version
        shutil.copytree(marketplace, repository, dirs_exist_ok=True)
        _run(
            ["git", "add", "--all"],
            cwd=repository,
            label="snapshot tree staging",
        )
        if same_version:
            existing_source_revision = existing.get("source_revision")
            if existing_source_revision != args.source_revision:
                raise ValueError("same version already points to a different source revision")
            candidate_tree = _run(
                ["git", "write-tree"],
                cwd=repository,
                label="candidate snapshot tree write",
            ).stdout.strip()
            if existing_tree != candidate_tree:
                raise ValueError("same version already has different Marketplace content")
            return {
                "ok": True,
                "action": "already_current",
                "snapshot_revision": expected_old_revision,
            }
        _run(
            [
                "git",
                "-c",
                "user.name=github-actions[bot]",
                "-c",
                "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                "-c",
                "commit.gpgSign=false",
                "commit",
                "--quiet",
                "-m",
                f"release: publish marketplace snapshot {args.version}",
            ],
            cwd=repository,
            label="snapshot commit creation",
        )
        revision = _run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            label="snapshot commit verification",
        ).stdout.strip()
        _run(
            ["git", "fetch", "--quiet", "--no-tags", str(repository), "HEAD"],
            cwd=caller_repository,
            label="snapshot import into caller repository",
        )
        imported_revision = _run(
            ["git", "rev-parse", "FETCH_HEAD"],
            cwd=caller_repository,
            label="imported snapshot verification",
        ).stdout.strip()
        if imported_revision != revision:
            raise ValueError("Imported Marketplace snapshot revision does not match candidate")
        _run(
            [
                "git",
                "push",
                f"--force-with-lease=refs/heads/{args.branch}:{expected_old_revision}",
                args.remote,
                f"{revision}:refs/heads/{args.branch}",
            ],
            cwd=caller_repository,
            label="Marketplace snapshot push",
        )
        if (
            _remote_revision(caller_repository, args.remote, args.branch)
            != revision
        ):
            raise ValueError("Marketplace remote verification failed after publish")

    return {"ok": True, "action": "published", "snapshot_revision": revision}


def main(argv: list[str] | None = None) -> int:
    try:
        result = publish(_arguments(argv))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
