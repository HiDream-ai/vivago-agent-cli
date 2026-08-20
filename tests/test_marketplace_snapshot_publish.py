from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = REPO_ROOT / "scripts" / "publish_marketplace_snapshot.py"


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


class MarketplaceSnapshotPublishTests(unittest.TestCase):
    def _remote(self, root: Path) -> Path:
        remote = root / "remote.git"
        result = _git("init", "--bare", str(remote))
        self.assertEqual(result.returncode, 0, result.stderr)
        return remote

    def _candidate(
        self,
        root: Path,
        *,
        version: str,
        revision: str,
        channel: str = "beta",
    ) -> Path:
        marketplace = root / f"candidate-{version}"
        plugin = marketplace / "plugins" / "vivago-agent-cli"
        plugin.mkdir(parents=True)
        profile = "prod" if channel == "beta" else "dev"
        (plugin / "BUILD_INFO.json").write_text(
            json.dumps(
                {
                    "version": version,
                    "source_revision": revision,
                    "channel": channel,
                    "profile": profile,
                }
            ),
            encoding="utf-8",
        )
        (plugin / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (plugin / "payload.txt").write_text(version, encoding="utf-8")
        return marketplace

    def _publish(
        self,
        marketplace: Path,
        remote: Path,
        *,
        version: str,
        revision: str,
        channel: str = "beta",
        branch: str = "marketplace",
        expected_old_revision: str | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        caller = remote.parent / "publisher-caller"
        if not caller.is_dir():
            caller.mkdir()
            initialized = _git("init", "--quiet", cwd=caller)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            added = _git("remote", "add", "snapshot-origin", str(remote), cwd=caller)
            self.assertEqual(added.returncode, 0, added.stderr)
        command = [
            sys.executable,
            str(PUBLISHER),
            "--marketplace",
            str(marketplace),
            "--remote",
            "snapshot-origin",
            "--branch",
            branch,
            "--channel",
            channel,
            "--version",
            version,
            "--source-revision",
            revision,
        ]
        if expected_old_revision is not None:
            command.extend(("--expected-old-revision", expected_old_revision))
        return subprocess.run(
            command,
            cwd=caller,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def test_initial_publish_creates_one_parentless_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = self._remote(root)
            revision = "a" * 40
            candidate = self._candidate(
                root,
                version="0.3.0-beta.1",
                revision=revision,
            )

            result = self._publish(
                candidate,
                remote,
                version="0.3.0-beta.1",
                revision=revision,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["action"], "published")
            count = _git(
                "--git-dir",
                str(remote),
                "rev-list",
                "--count",
                "refs/heads/marketplace",
            )
            self.assertEqual(count.returncode, 0, count.stderr)
            self.assertEqual(count.stdout.strip(), "1")
            parents = _git(
                "--git-dir",
                str(remote),
                "rev-list",
                "--parents",
                "-n",
                "1",
                "refs/heads/marketplace",
            )
            self.assertEqual(parents.returncode, 0, parents.stderr)
            self.assertEqual(len(parents.stdout.split()), 1)

    def test_second_publish_replaces_history_with_one_new_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = self._remote(root)
            first = self._candidate(
                root,
                version="0.3.0-beta.1",
                revision="a" * 40,
            )
            second = self._candidate(
                root,
                version="0.3.0-beta.2",
                revision="b" * 40,
            )
            first_result = self._publish(
                first,
                remote,
                version="0.3.0-beta.1",
                revision="a" * 40,
            )
            self.assertEqual(first_result.returncode, 0, first_result.stderr)

            second_result = self._publish(
                second,
                remote,
                version="0.3.0-beta.2",
                revision="b" * 40,
            )

            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            count = _git(
                "--git-dir",
                str(remote),
                "rev-list",
                "--count",
                "refs/heads/marketplace",
            )
            self.assertEqual(count.returncode, 0, count.stderr)
            self.assertEqual(count.stdout.strip(), "1")
            payload = _git(
                "--git-dir",
                str(remote),
                "show",
                "refs/heads/marketplace:plugins/vivago-agent-cli/payload.txt",
            )
            self.assertEqual(payload.returncode, 0, payload.stderr)
            self.assertEqual(payload.stdout, "0.3.0-beta.2")

    def test_older_version_cannot_replace_newer_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = self._remote(root)
            newer = self._candidate(
                root,
                version="0.3.0-beta.2",
                revision="b" * 40,
            )
            older = self._candidate(
                root,
                version="0.3.0-beta.1",
                revision="a" * 40,
            )
            published = self._publish(
                newer,
                remote,
                version="0.3.0-beta.2",
                revision="b" * 40,
            )
            self.assertEqual(published.returncode, 0, published.stderr)
            before = _git(
                "--git-dir",
                str(remote),
                "rev-parse",
                "refs/heads/marketplace",
            ).stdout.strip()

            result = self._publish(
                older,
                remote,
                version="0.3.0-beta.1",
                revision="a" * 40,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("newer", result.stderr)
            after = _git(
                "--git-dir",
                str(remote),
                "rev-parse",
                "refs/heads/marketplace",
            ).stdout.strip()
            self.assertEqual(after, before)

    def test_same_version_revision_and_tree_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = self._remote(root)
            revision = "c" * 40
            candidate = self._candidate(
                root,
                version="0.3.0-beta.3",
                revision=revision,
            )
            first = self._publish(
                candidate,
                remote,
                version="0.3.0-beta.3",
                revision=revision,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            before = _git(
                "--git-dir",
                str(remote),
                "rev-parse",
                "refs/heads/marketplace",
            ).stdout.strip()

            second = self._publish(
                candidate,
                remote,
                version="0.3.0-beta.3",
                revision=revision,
            )

            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout)["action"], "already_current")
            after = _git(
                "--git-dir",
                str(remote),
                "rev-parse",
                "refs/heads/marketplace",
            ).stdout.strip()
            self.assertEqual(after, before)

    def test_candidate_build_info_must_match_publish_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = self._remote(root)
            candidate = self._candidate(
                root,
                version="0.3.0-beta.1",
                revision="d" * 40,
            )

            result = self._publish(
                candidate,
                remote,
                version="0.3.0-beta.1",
                revision="e" * 40,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BUILD_INFO.json", result.stderr)
            branch = _git(
                "--git-dir",
                str(remote),
                "show-ref",
                "--verify",
                "refs/heads/marketplace",
            )
            self.assertNotEqual(branch.returncode, 0)

    def test_stale_expected_revision_cannot_overwrite_remote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = self._remote(root)
            first = self._candidate(
                root,
                version="0.3.0-beta.1",
                revision="1" * 40,
            )
            second = self._candidate(
                root,
                version="0.3.0-beta.2",
                revision="2" * 40,
            )
            stale = self._candidate(
                root,
                version="0.3.0-beta.3",
                revision="3" * 40,
            )
            first_result = self._publish(
                first,
                remote,
                version="0.3.0-beta.1",
                revision="1" * 40,
            )
            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            stale_revision = _git(
                "--git-dir",
                str(remote),
                "rev-parse",
                "refs/heads/marketplace",
            ).stdout.strip()
            second_result = self._publish(
                second,
                remote,
                version="0.3.0-beta.2",
                revision="2" * 40,
            )
            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            current_revision = _git(
                "--git-dir",
                str(remote),
                "rev-parse",
                "refs/heads/marketplace",
            ).stdout.strip()

            result = self._publish(
                stale,
                remote,
                version="0.3.0-beta.3",
                revision="3" * 40,
                expected_old_revision=stale_revision,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("changed", result.stderr)
            after = _git(
                "--git-dir",
                str(remote),
                "rev-parse",
                "refs/heads/marketplace",
            ).stdout.strip()
            self.assertEqual(after, current_revision)

    def test_publish_fails_when_remote_does_not_retain_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = self._remote(root)
            alternate = self._candidate(
                root,
                version="0.3.0-beta.9",
                revision="9" * 40,
            )
            alternate_result = self._publish(
                alternate,
                remote,
                version="0.3.0-beta.9",
                revision="9" * 40,
                branch="alternate",
            )
            self.assertEqual(alternate_result.returncode, 0, alternate_result.stderr)
            alternate_revision = _git(
                "--git-dir",
                str(remote),
                "rev-parse",
                "refs/heads/alternate",
            ).stdout.strip()
            hook = remote / "hooks" / "post-receive"
            hook.write_text(
                "#!/bin/sh\n"
                f"git update-ref refs/heads/marketplace {alternate_revision}\n",
                encoding="utf-8",
            )
            hook.chmod(hook.stat().st_mode | 0o111)
            candidate = self._candidate(
                root,
                version="0.3.0-beta.1",
                revision="1" * 40,
            )

            result = self._publish(
                candidate,
                remote,
                version="0.3.0-beta.1",
                revision="1" * 40,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("verification", result.stderr)

    def test_snapshot_commit_ignores_global_signing_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = self._remote(root)
            candidate = self._candidate(
                root,
                version="0.3.0-beta.1",
                revision="a" * 40,
            )
            env = dict(os.environ)
            env.update(
                {
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "commit.gpgSign",
                    "GIT_CONFIG_VALUE_0": "true",
                }
            )

            result = self._publish(
                candidate,
                remote,
                version="0.3.0-beta.1",
                revision="a" * 40,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_named_remote_push_runs_from_authenticated_caller_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = self._remote(root)
            caller = root / "caller"
            caller.mkdir()
            initialized = _git("init", "--quiet", cwd=caller)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            added = _git("remote", "add", "origin", str(remote), cwd=caller)
            self.assertEqual(added.returncode, 0, added.stderr)
            marker = root / "caller-pre-push-ran"
            hook = caller / ".git" / "hooks" / "pre-push"
            hook.write_text(
                "#!/bin/sh\n" f'printf called > "{marker}"\n',
                encoding="utf-8",
            )
            hook.chmod(hook.stat().st_mode | 0o111)
            revision = "f" * 40
            candidate = self._candidate(
                root,
                version="0.3.0-beta.1",
                revision=revision,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PUBLISHER),
                    "--marketplace",
                    str(candidate),
                    "--remote",
                    "origin",
                    "--branch",
                    "marketplace",
                    "--channel",
                    "beta",
                    "--version",
                    "0.3.0-beta.1",
                    "--source-revision",
                    revision,
                ],
                cwd=caller,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(marker.is_file())


if __name__ == "__main__":
    unittest.main()
