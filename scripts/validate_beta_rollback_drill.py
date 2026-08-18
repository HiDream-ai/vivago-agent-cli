#!/usr/bin/env python3
"""Validate the company-only temporary Beta rollback drill boundary."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass

from release_policy import BETA_VERSION, validate_beta


POSITIVE_INTEGER = re.compile(r"^[1-9]\d*$")
BRANCH_PREFIX = "drill/marketplace"


@dataclass(frozen=True)
class DrillPlan:
    incident_version: str
    recovery_version: str
    repository: str
    ref: str
    incident_revision: str
    recovery_revision: str
    branch: str
    run_id: str
    run_attempt: str


def _beta_parts(value: str) -> tuple[int, int, int, int]:
    match = BETA_VERSION.fullmatch(value)
    if match is None:
        raise ValueError("version must match X.Y.Z-beta.N with N greater than zero")
    return tuple(int(part) for part in match.groups())


def expected_branch(run_id: str, run_attempt: str) -> str:
    if not POSITIVE_INTEGER.fullmatch(run_id):
        raise ValueError("run ID must be a positive integer")
    if not POSITIVE_INTEGER.fullmatch(run_attempt):
        raise ValueError("run attempt must be a positive integer")
    return f"{BRANCH_PREFIX}-{run_id}-{run_attempt}"


def validate_plan(plan: DrillPlan) -> None:
    validate_beta(
        plan.incident_version,
        plan.repository,
        plan.ref,
        plan.incident_revision,
    )
    validate_beta(
        plan.recovery_version,
        plan.repository,
        plan.ref,
        plan.recovery_revision,
    )
    incident = _beta_parts(plan.incident_version)
    recovery = _beta_parts(plan.recovery_version)
    if incident[:3] != recovery[:3]:
        raise ValueError("incident and recovery versions must use the same release line")
    if recovery <= incident:
        raise ValueError("recovery version must be strictly newer than incident version")
    if plan.recovery_revision.lower() == plan.incident_revision.lower():
        raise ValueError("incident and recovery source revisions must differ")
    expected = expected_branch(plan.run_id, plan.run_attempt)
    if plan.branch != expected:
        raise ValueError(f"temporary branch must be {expected}")


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--incident-version", required=True)
    plan.add_argument("--recovery-version", required=True)
    plan.add_argument("--repository", required=True)
    plan.add_argument("--ref", required=True)
    plan.add_argument("--incident-revision", required=True)
    plan.add_argument("--recovery-revision", required=True)
    plan.add_argument("--branch", required=True)
    plan.add_argument("--run-id", required=True)
    plan.add_argument("--run-attempt", required=True)
    return parser.parse_args(argv)


def plan_from_args(args: argparse.Namespace) -> DrillPlan:
    return DrillPlan(
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


def main(argv: list[str] | None = None) -> int:
    try:
        args = _arguments(argv)
        plan = plan_from_args(args)
        validate_plan(plan)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {"ok": True, "action": "run_drill", "branch": plan.branch},
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
