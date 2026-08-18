#!/usr/bin/env python3
"""Run and clean an isolated Marketplace rollback drill using a temporary branch."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from validate_beta_marketplace_update import validate as validate_marketplace_update
from validate_beta_rollback_drill import DrillPlan, validate_plan


MAX_ELAPSED_SECONDS = 30 * 60
BUILD_INFO = Path("plugins/vivago-agent-cli/BUILD_INFO.json")


class DrillError(RuntimeError):
    pass


def _git_operation(arguments: list[str]) -> str:
    index = 0
    while index < len(arguments):
        if arguments[index] == "-c" and index + 1 < len(arguments):
            index += 2
            continue
        if not arguments[index].startswith("-"):
            return arguments[index]
        index += 1
    return "command"


def _safe_git_diagnostic(stderr: str) -> str:
    line = next((value.strip() for value in stderr.splitlines() if value.strip()), "")
    line = re.sub(r"https?://\S+", "[redacted-url]", line)
    line = re.sub(
        r"(?i)(authorization|cookie|refresh[_ -]?token|access[_ -]?token)(\s*[:=]\s*)\S+",
        r"\1\2[redacted]",
        line,
    )
    return line[:300]


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incident-marketplace", type=Path, required=True)
    parser.add_argument("--recovery-marketplace", type=Path, required=True)
    parser.add_argument("--incident-version", required=True)
    parser.add_argument("--recovery-version", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--incident-revision", required=True)
    parser.add_argument("--recovery-revision", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--started-at-epoch", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def _run_git(
    repository: Path, arguments: list[str], *, allow_failure: bool = False
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 and not allow_failure:
        operation = _git_operation(arguments)
        diagnostic = _safe_git_diagnostic(result.stderr)
        suffix = f": {diagnostic}" if diagnostic else ""
        raise DrillError(
            f"git {operation} failed (exit {result.returncode}){suffix}"
        )
    return result


def _read_build_info(
    marketplace: Path, *, version: str, revision: str, label: str
) -> dict[str, object]:
    path = marketplace / BUILD_INFO
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DrillError(f"{label} Marketplace metadata is unreadable") from exc
    expected = {
        "version": version,
        "source_revision": revision.lower(),
        "channel": "beta",
        "profile": "prod",
    }
    actual = {
        "version": value.get("version") if isinstance(value, dict) else None,
        "source_revision": (
            str(value.get("source_revision", "")).lower()
            if isinstance(value, dict)
            else None
        ),
        "channel": value.get("channel") if isinstance(value, dict) else None,
        "profile": value.get("profile") if isinstance(value, dict) else None,
    }
    if actual != expected:
        raise DrillError(f"{label} Marketplace metadata does not match the drill plan")
    return value


def _replace_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise DrillError("Marketplace input directory is missing")
    for child in destination.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir() and not child.is_symlink():
            shutil.copytree(child, target, copy_function=shutil.copy2)
        else:
            shutil.copy2(child, target, follow_symlinks=False)


def _remote_head(repository: Path, remote: str, branch: str) -> str | None:
    result = _run_git(
        repository,
        ["ls-remote", "--heads", remote, f"refs/heads/{branch}"],
    )
    line = result.stdout.strip()
    if not line:
        return None
    fields = line.split()
    if len(fields) != 2 or fields[1] != f"refs/heads/{branch}":
        raise DrillError("temporary branch lookup returned an unexpected result")
    return fields[0].lower()


def _commit(repository: Path, message: str) -> str:
    _run_git(repository, ["add", "--all"])
    _run_git(
        repository,
        [
            "-c",
            "user.name=github-actions[bot]",
            "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            message,
        ],
    )
    return _run_git(repository, ["rev-parse", "HEAD"]).stdout.strip().lower()


def _write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> dict[str, object]:
    plan = DrillPlan(
        incident_version=args.incident_version,
        recovery_version=args.recovery_version,
        repository=args.repository,
        ref=args.ref,
        incident_revision=args.incident_revision,
        recovery_revision=args.recovery_revision,
        branch=args.branch,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
    )
    validate_plan(plan)
    if args.started_at_epoch <= 0:
        raise DrillError("started-at epoch must be positive")
    repository_root = args.repository_root.resolve()
    if not (repository_root / ".git").exists():
        raise DrillError("repository root must be a Git worktree")

    _read_build_info(
        args.incident_marketplace,
        version=plan.incident_version,
        revision=plan.incident_revision,
        label="incident",
    )

    report: dict[str, object] = {
        "branch": plan.branch,
        "cleanup": "not_required",
        "elapsed_seconds": None,
        "incident_commit": None,
        "incident_revision": plan.incident_revision.lower(),
        "incident_version": plan.incident_version,
        "recovery_commit": None,
        "recovery_parent": None,
        "recovery_revision": plan.recovery_revision.lower(),
        "recovery_version": plan.recovery_version,
        "status": "failed",
    }
    worktree_path: Path | None = None
    branch_created = False
    failure: Exception | None = None

    try:
        with tempfile.TemporaryDirectory(prefix="vivago-beta-rollback-") as directory:
            worktree_path = Path(directory) / "marketplace"
            _run_git(
                repository_root,
                ["worktree", "add", "--detach", str(worktree_path), "HEAD"],
            )
            _run_git(worktree_path, ["checkout", "--orphan", plan.branch])
            _replace_tree(args.incident_marketplace.resolve(), worktree_path)
            incident_commit = _commit(
                worktree_path, f"drill: stage {plan.incident_version}"
            )
            report["incident_commit"] = incident_commit
            _run_git(
                worktree_path,
                ["push", args.remote, f"HEAD:refs/heads/{plan.branch}"],
            )
            branch_created = True
            if _remote_head(repository_root, args.remote, plan.branch) != incident_commit:
                raise DrillError("incident commit was not confirmed on the temporary branch")

            _read_build_info(
                args.recovery_marketplace,
                version=plan.recovery_version,
                revision=plan.recovery_revision,
                label="recovery",
            )
            update_args = argparse.Namespace(
                candidate_version=plan.recovery_version,
                candidate_revision=plan.recovery_revision,
                existing_build_info=worktree_path / BUILD_INFO,
            )
            if validate_marketplace_update(update_args) != "update":
                raise DrillError("recovery Marketplace did not produce a forward update")

            _replace_tree(args.recovery_marketplace.resolve(), worktree_path)
            recovery_commit = _commit(
                worktree_path, f"drill: recover with {plan.recovery_version}"
            )
            recovery_parent = _run_git(
                worktree_path, ["rev-parse", "HEAD^"]
            ).stdout.strip().lower()
            report["recovery_commit"] = recovery_commit
            report["recovery_parent"] = recovery_parent
            if recovery_parent != incident_commit:
                raise DrillError("recovery commit is not a fast-forward child of incident")
            _run_git(
                worktree_path,
                ["push", args.remote, f"HEAD:refs/heads/{plan.branch}"],
            )
            if _remote_head(repository_root, args.remote, plan.branch) != recovery_commit:
                raise DrillError("recovery commit was not confirmed on the temporary branch")

            elapsed = max(int(time.time()) - args.started_at_epoch, 0)
            report["elapsed_seconds"] = elapsed
            if elapsed > MAX_ELAPSED_SECONDS:
                raise DrillError("recovery exceeded the 30-minute objective")
            report["status"] = "passed"
    except (DrillError, OSError, ValueError, json.JSONDecodeError) as exc:
        failure = exc
    finally:
        try:
            if branch_created or _remote_head(repository_root, args.remote, plan.branch):
                _run_git(repository_root, ["push", args.remote, "--delete", plan.branch])
                report["cleanup"] = "deleted"
            if _remote_head(repository_root, args.remote, plan.branch) is not None:
                raise DrillError("temporary branch still exists after cleanup")
        except (DrillError, OSError) as exc:
            report["cleanup"] = "failed"
            if failure is None:
                failure = exc
        if worktree_path is not None:
            _run_git(
                repository_root,
                ["worktree", "remove", "--force", str(worktree_path)],
                allow_failure=True,
            )
            _run_git(repository_root, ["worktree", "prune"], allow_failure=True)
        if failure is not None:
            report["status"] = "failed"
            if report["elapsed_seconds"] is None:
                report["elapsed_seconds"] = max(
                    int(time.time()) - args.started_at_epoch, 0
                )
        _write_report(args.report, report)

    if failure is not None:
        raise DrillError(str(failure))
    return report


def main(argv: list[str] | None = None) -> int:
    try:
        report = run(_arguments(argv))
    except (DrillError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "data": report}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
