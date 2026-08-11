from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _workflow(name: str) -> str:
    path = WORKFLOWS / name
    if not path.is_file():
        raise AssertionError(f"missing GitHub Actions workflow: {path.relative_to(REPO_ROOT)}")
    return path.read_text(encoding="utf-8")


class GitHubWorkflowContractTests(unittest.TestCase):
    def test_development_workflows_are_bound_to_personal_repository(self) -> None:
        personal_guard = "github.repository == 'ChaoXia-Beginer/vivago-agent-cli'"
        for name in ("ci.yml", "dev-release.yml", "hosted-l3.yml"):
            with self.subTest(workflow=name):
                self.assertIn(personal_guard, _workflow(name))

    def test_ci_runs_native_smoke_on_all_six_supported_targets(self) -> None:
        text = _workflow("ci.yml")

        self.assertRegex(text, r"(?m)^  native-platform-smoke:\s*$")
        self.assertRegex(
            text,
            r"(?m)^    needs: quality-and-package\s*$",
        )
        self.assertRegex(
            text,
            r"(?m)^    if: github\.repository == 'ChaoXia-Beginer/vivago-agent-cli' && github\.event_name == 'workflow_dispatch'\s*$",
        )
        self.assertIn("fail-fast: false", text)
        expected_matrix = {
            "darwin-arm64": "macos-26",
            "darwin-amd64": "macos-26-intel",
            "linux-arm64": "ubuntu-24.04-arm",
            "linux-amd64": "ubuntu-24.04",
            "windows-arm64": "windows-11-arm",
            "windows-amd64": "windows-2025",
        }
        for target, runner in expected_matrix.items():
            with self.subTest(target=target):
                self.assertRegex(
                    text,
                    rf"(?s)- target: {re.escape(target)}\s+runner: {re.escape(runner)}",
                )

        action_refs = re.findall(r"uses:\s*[^\s@]+@([^\s#]+)", text)
        self.assertTrue(action_refs)
        for reference in action_refs:
            self.assertRegex(reference, r"^[0-9a-f]{40}$")
        self.assertNotIn("riscv64", text)
        self.assertIn("scripts/verify_native_platform.py", text)
        self.assertIn("--expected-target \"${{ matrix.target }}\"", text)
        self.assertIn("actions/download-artifact@", text)
        self.assertIn("actions/upload-artifact@", text)

    def test_workflows_do_not_use_runner_context_in_job_level_environment(self) -> None:
        for name in ("ci.yml", "dev-release.yml", "hosted-l3.yml"):
            with self.subTest(workflow=name):
                text = _workflow(name)
                self.assertNotIn("${{ runner.temp }}", text)
                self.assertIn("${{ github.workspace }}/.ci-", text)

    def test_workflows_point_setup_python_cache_at_the_dev_requirements(self) -> None:
        for name in ("ci.yml", "dev-release.yml"):
            with self.subTest(workflow=name):
                text = _workflow(name)
                self.assertEqual(
                    text.count("cache-dependency-path: requirements-dev.txt"),
                    1,
                )

    def test_ci_is_read_only_and_runs_the_complete_development_gate(self) -> None:
        text = _workflow("ci.yml")

        self.assertRegex(text, r"(?m)^on:\s*$")
        for trigger in ("pull_request", "push", "workflow_dispatch"):
            self.assertRegex(text, rf"(?m)^  {trigger}:\s*$")
        self.assertRegex(text, r"(?m)^      - dev-marketplace\s*$")
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\s*$")
        for command in (
            "go test ./...",
            "go test -tags prod ./...",
            "go test -race ./...",
            "go vet ./...",
            "python -m unittest",
            "scripts/build_go_binaries.py",
            "scripts/assemble_go_distribution.py",
            "scripts/verify_dev_distribution.py",
            "claude plugin validate",
        ):
            self.assertIn(command, text)
        self.assertIn("actions/upload-artifact@", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("gh release", text)
        self.assertNotIn("git push", text)

        action_refs = re.findall(r"uses:\s*[^\s@]+@([^\s#]+)", text)
        self.assertTrue(action_refs)
        for reference in action_refs:
            self.assertRegex(reference, r"^[0-9a-f]{40}$")

    def test_ci_pins_the_official_codex_validator_by_revision_and_checksum(self) -> None:
        text = _workflow("ci.yml")

        self.assertIn(
            "raw.githubusercontent.com/openai/codex/"
            "e75a1888d7e91ce56fc90d0edd32a9e6a8974686/",
            text,
        )
        self.assertIn(
            "ebda00d55d7518b127f675f062fb5c6e7a1ffdc0a99df1a55ac594400d7d3228",
            text,
        )
        self.assertIn("sha256sum --check", text)
        self.assertNotIn("python scripts/validate_plugin.py", text)

    def test_dev_release_is_manual_serialized_and_dev_only(self) -> None:
        text = _workflow("dev-release.yml")

        self.assertRegex(text, r"(?m)^on:\n  workflow_dispatch:\s*$")
        self.assertNotRegex(text, r"(?m)^  (push|pull_request):")
        self.assertRegex(text, r"(?m)^      version:\s*$")
        self.assertRegex(text, r"(?m)^        required: true\s*$")
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\s*$")
        self.assertRegex(text, r"(?m)^    permissions:\n      contents: write\s*$")
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("-dev.", text)
        self.assertIn("dev-marketplace", text)
        self.assertIn("scripts/validate_dev_release_policy.py", text)
        self.assertIn('--repository "${{ github.repository }}"', text)
        self.assertIn('--ref "${{ github.ref }}"', text)
        self.assertIn('--source-revision "${GITHUB_SHA}"', text)
        self.assertIn("gh release create", text)
        self.assertIn("--prerelease", text)
        self.assertRegex(text, r"git[^\n]* push origin HEAD:dev-marketplace")
        self.assertNotIn("--force", text)
        self.assertNotRegex(text, r"(?m)^      profile:\s*$")

        for command in (
            "go test ./...",
            "go test -tags prod ./...",
            "go test -race ./...",
            "go vet ./...",
            "python -m unittest",
            "scripts/build_go_binaries.py",
            "scripts/assemble_go_distribution.py",
            "scripts/verify_dev_distribution.py",
            "claude plugin validate",
        ):
            self.assertIn(command, text)
        self.assertIn("actions/upload-artifact@", text)
        self.assertIn("actions/download-artifact@", text)

        action_refs = re.findall(r"uses:\s*[^\s@]+@([^\s#]+)", text)
        self.assertTrue(action_refs)
        for reference in action_refs:
            self.assertRegex(reference, r"^[0-9a-f]{40}$")

    def test_dev_release_gates_publish_on_twelve_host_lifecycle_cases(self) -> None:
        text = _workflow("dev-release.yml")

        self.assertRegex(text, r"(?m)^  host-plugin-lifecycle:\s*$")
        self.assertIn("fail-fast: false", text)
        self.assertIn("scripts/verify_host_plugin_lifecycle.py", text)
        self.assertIn("@openai/codex@0.147.0", text)
        self.assertIn("@anthropic-ai/claude-code@2.1.220", text)
        expected_matrix = {
            "darwin-arm64": "macos-26",
            "darwin-amd64": "macos-26-intel",
            "linux-arm64": "ubuntu-24.04-arm",
            "linux-amd64": "ubuntu-24.04",
            "windows-arm64": "windows-11-arm",
            "windows-amd64": "windows-2025",
        }
        for target, runner in expected_matrix.items():
            for host in ("codex", "claude-code"):
                with self.subTest(target=target, host=host):
                    self.assertRegex(
                        text,
                        rf"(?s)- target: {re.escape(target)}\s+runner: {re.escape(runner)}\s+host: {re.escape(host)}",
                    )
        self.assertRegex(
            text,
            r"(?m)^    needs: \[build, host-plugin-lifecycle\]\s*$",
        )
        self.assertIn("host-lifecycle-${{ matrix.target }}-${{ matrix.host }}", text)

    def test_dev_release_preserves_worktree_metadata_and_fails_closed_on_tag_lookup(self) -> None:
        text = _workflow("dev-release.yml")

        self.assertIn("rsync -a --delete --exclude=.git ", text)
        self.assertNotIn("--exclude=.git/", text)
        self.assertIn("tag_lookup_status=$?", text)
        self.assertIn("case \"${tag_lookup_status}\" in", text)
        self.assertRegex(text, r"(?s)case \"\$\{tag_lookup_status\}\" in.*0\).*2\).*\*\)")

    def test_hosted_l3_is_manual_ticket_only_and_covers_six_native_targets(self) -> None:
        text = _workflow("hosted-l3.yml")

        self.assertRegex(text, r"(?m)^on:\n  workflow_dispatch:\s*$")
        self.assertNotRegex(text, r"(?m)^  (push|pull_request):")
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertNotIn("feature/go-public-beta", text)
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\s*$")
        self.assertIn("environment: overseas-test-e2e", text)
        self.assertIn("secrets.VIVAGO_E2E_TICKET", text)
        self.assertNotIn("REFRESH_TOKEN", text)
        self.assertNotIn("refresh_token", text.lower())
        self.assertIn("./cmd/vivago-e2e-auth seed", text)
        self.assertIn("scripts/verify_hosted_l3.py", text)
        self.assertIn("@openai/codex@0.147.0", text)
        self.assertIn("@anthropic-ai/claude-code@2.1.220", text)
        self.assertIn("fail-fast: false", text)
        self.assertIn("max-parallel: 1", text)
        self.assertNotRegex(text, r"run:[^\n]*\$\{\{ inputs\.")

        expected_matrix = {
            "darwin-arm64": "macos-26",
            "darwin-amd64": "macos-26-intel",
            "linux-arm64": "ubuntu-24.04-arm",
            "linux-amd64": "ubuntu-24.04",
            "windows-arm64": "windows-11-arm",
            "windows-amd64": "windows-2025",
        }
        for target, runner in expected_matrix.items():
            with self.subTest(target=target):
                self.assertRegex(
                    text,
                    rf"(?s)- target: {re.escape(target)}\s+runner: {re.escape(runner)}",
                )

        action_refs = re.findall(r"uses:\s*[^\s@]+@([^\s#]+)", text)
        self.assertTrue(action_refs)
        for reference in action_refs:
            self.assertRegex(reference, r"^[0-9a-f]{40}$")

    def test_beta_check_is_company_only_read_only_and_builds_production_package(self) -> None:
        text = _workflow("beta-check.yml")

        for trigger in ("pull_request", "push", "workflow_dispatch"):
            self.assertRegex(text, rf"(?m)^  {trigger}:")
        self.assertIn("github.repository == 'HiDream-ai/vivago-agent-cli'", text)
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\s*$")
        for command in (
            "go test ./...",
            "go test -tags prod ./...",
            "go test -race ./...",
            "go vet ./...",
            "python -m unittest",
            "scripts/build_beta_binaries.py",
            "scripts/assemble_beta_distribution.py",
            "scripts/verify_beta_distribution.py",
            "claude plugin validate",
        ):
            self.assertIn(command, text)
        self.assertIn("actions/upload-artifact@", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("gh release", text)
        self.assertNotIn("git push", text)

    def test_beta_workflows_run_native_production_smoke_on_all_six_targets(self) -> None:
        expected_matrix = {
            "darwin-arm64": "macos-26",
            "darwin-amd64": "macos-26-intel",
            "linux-arm64": "ubuntu-24.04-arm",
            "linux-amd64": "ubuntu-24.04",
            "windows-arm64": "windows-11-arm",
            "windows-amd64": "windows-2025",
        }
        for workflow in ("beta-check.yml", "beta-release.yml"):
            with self.subTest(workflow=workflow):
                text = _workflow(workflow)
                self.assertRegex(text, r"(?m)^  native-platform-smoke:\s*$")
                self.assertIn("fail-fast: false", text)
                self.assertIn("scripts/verify_beta_native_platform.py", text)
                self.assertIn('--expected-target "${{ matrix.target }}"', text)
                self.assertIn("actions/download-artifact@", text)
                self.assertIn("actions/upload-artifact@", text)
                for target, runner in expected_matrix.items():
                    self.assertRegex(
                        text,
                        rf"(?s)- target: {re.escape(target)}\s+runner: {re.escape(runner)}",
                    )

        release = _workflow("beta-release.yml")
        self.assertRegex(
            release,
            r"(?m)^    needs: \[build, native-platform-smoke, host-plugin-lifecycle\]\s*$",
        )

    def test_beta_workflows_gate_on_twelve_host_lifecycle_cases(self) -> None:
        expected_matrix = {
            "darwin-arm64": "macos-26",
            "darwin-amd64": "macos-26-intel",
            "linux-arm64": "ubuntu-24.04-arm",
            "linux-amd64": "ubuntu-24.04",
            "windows-arm64": "windows-11-arm",
            "windows-amd64": "windows-2025",
        }
        for workflow in ("beta-check.yml", "beta-release.yml"):
            with self.subTest(workflow=workflow):
                text = _workflow(workflow)
                self.assertRegex(text, r"(?m)^  host-plugin-lifecycle:\s*$")
                self.assertIn("scripts/derive_previous_beta_version.py", text)
                self.assertIn("scripts/verify_beta_host_plugin_lifecycle.py", text)
                self.assertIn("@openai/codex@0.147.0", text)
                self.assertIn("@anthropic-ai/claude-code@2.1.220", text)
                self.assertIn("--previous-marketplace", text)
                self.assertIn("fail-fast: false", text)
                for target, runner in expected_matrix.items():
                    for host in ("codex", "claude-code"):
                        self.assertRegex(
                            text,
                            rf"(?s)- target: {re.escape(target)}\s+runner: {re.escape(runner)}\s+host: {re.escape(host)}",
                        )

    def test_beta_host_lifecycle_extraction_is_windows_path_safe(self) -> None:
        for workflow in ("beta-check.yml", "beta-release.yml"):
            with self.subTest(workflow=workflow):
                text = _workflow(workflow)
                self.assertNotIn('tar -xzf "${HOST_ROOT}/input/', text)
                self.assertIn(
                    'python -m tarfile -e "${HOST_ROOT}/input/vivago-beta-previous.tar.gz"',
                    text,
                )

    def test_release_workflows_use_one_cross_platform_archive_extractor(self) -> None:
        for workflow in ("dev-release.yml", "beta-check.yml", "beta-release.yml"):
            with self.subTest(workflow=workflow):
                self.assertNotIn("tar -xzf", _workflow(workflow))

    def test_beta_release_is_manual_company_main_only_and_has_protected_publish(self) -> None:
        text = _workflow("beta-release.yml")

        self.assertRegex(text, r"(?m)^on:\n  workflow_dispatch:\s*$")
        self.assertNotRegex(text, r"(?m)^  (push|pull_request):")
        self.assertRegex(text, r"(?m)^      version:\s*$")
        for forbidden_input in ("profile", "api_url", "login_url", "web_url", "channel"):
            self.assertNotRegex(text, rf"(?m)^      {forbidden_input}:\s*$")
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\s*$")
        self.assertIn("scripts/validate_beta_release_policy.py", text)
        self.assertIn('--repository "${{ github.repository }}"', text)
        self.assertIn('--ref "${{ github.ref }}"', text)
        self.assertIn('--source-revision "${GITHUB_SHA}"', text)
        self.assertIn("scripts/build_beta_binaries.py", text)
        self.assertIn("scripts/assemble_beta_distribution.py", text)
        self.assertIn("scripts/verify_beta_distribution.py", text)
        self.assertIn("environment: production-beta", text)
        self.assertRegex(text, r"(?m)^    permissions:\n      contents: write\s*$")
        self.assertIn("gh release create", text)
        self.assertIn("--prerelease", text)
        self.assertRegex(text, r"git[^\n]* push origin HEAD:marketplace")
        self.assertNotIn("--force", text)
        self.assertIn("tag_lookup_status=$?", text)
        self.assertIn("case \"${tag_lookup_status}\" in", text)
        self.assertIn("cancel-in-progress: false", text)

        action_refs = re.findall(r"uses:\s*[^\s@]+@([^\s#]+)", text)
        self.assertTrue(action_refs)
        for reference in action_refs:
            self.assertRegex(reference, r"^[0-9a-f]{40}$")

    def test_beta_workflows_generate_sbom_and_release_attestations(self) -> None:
        for workflow in ("beta-check.yml", "beta-release.yml"):
            with self.subTest(workflow=workflow):
                text = _workflow(workflow)
                self.assertIn("scripts/generate_spdx_sbom.py", text)
                self.assertIn("SBOM.spdx.json", text)

        release = _workflow("beta-release.yml")
        self.assertIn(
            "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6",
            release,
        )
        for permission in (
            "id-token: write",
            "attestations: write",
            "artifact-metadata: write",
        ):
            self.assertIn(permission, release)
        self.assertIn("subject-path: ${{ env.ARCHIVE }}", release)
        self.assertIn("sbom-path: ${{ env.MARKETPLACE }}/SBOM.spdx.json", release)

    def test_beta_release_can_safely_resume_after_partial_publish(self) -> None:
        text = _workflow("beta-release.yml")

        self.assertIn("scripts/validate_beta_release_state.py", text)
        self.assertIn("scripts/validate_beta_marketplace_update.py", text)
        self.assertIn("gh release view", text)
        self.assertIn("steps.release_state.outputs.create_release == 'true'", text)
        self.assertIn("refs/heads/marketplace", text)
        self.assertIn("checkout --orphan marketplace", text)
        self.assertNotIn("Reject an existing immutable release tag", text)
        self.assertNotIn("release tag already exists and will not be overwritten", text)


if __name__ == "__main__":
    unittest.main()
