from __future__ import annotations

import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "verify_hosted_l3.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_hosted_l3", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load hosted L3 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HostedL3VerifierTests(unittest.TestCase):
    def test_profile_contracts_are_fixed_and_environment_specific(self) -> None:
        verifier = _load_module()

        self.assertEqual(
            verifier.profile_contract("dev"),
            {
                "profile": "dev",
                "channel": "dev",
                "environment": "overseas-test",
                "marketplace": "vivago-dev",
                "plugin_id": "vivago-agent-cli@vivago-dev",
                "web_host": "dev.vivago.ai",
            },
        )
        self.assertEqual(
            verifier.profile_contract("prod"),
            {
                "profile": "prod",
                "channel": "beta",
                "environment": "overseas-production",
                "marketplace": "vivago",
                "plugin_id": "vivago-agent-cli@vivago",
                "web_host": "vivago.ai",
            },
        )
        with self.assertRaisesRegex(ValueError, "unsupported profile"):
            verifier.profile_contract("staging")

    def test_arguments_can_select_production_codex_attachment_scope(self) -> None:
        verifier = _load_module()

        args = verifier.arguments(
            [
                "--marketplace",
                "/tmp/marketplace",
                "--expected-target",
                "darwin-arm64",
                "--expected-version",
                "0.3.0-beta.1",
                "--source-revision",
                "a" * 40,
                "--run-id",
                "123",
                "--report",
                "/tmp/report.json",
                "--expected-profile",
                "prod",
                "--host",
                "codex",
                "--scope",
                "attachment-artifact",
            ]
        )

        self.assertEqual(args.expected_profile, "prod")
        self.assertEqual(args.hosts, ["codex"])
        self.assertEqual(args.scope, "attachment-artifact")

    def test_supported_targets_and_hosts_match_public_beta_matrix(self) -> None:
        verifier = _load_module()

        self.assertEqual(
            verifier.TARGETS,
            (
                "darwin-arm64",
                "darwin-amd64",
                "linux-arm64",
                "linux-amd64",
                "windows-arm64",
                "windows-amd64",
            ),
        )
        self.assertEqual(verifier.HOSTS, ("codex", "claude-code"))

    def test_parse_finished_stream_returns_only_safe_identifiers(self) -> None:
        verifier = _load_module()
        records = [
            {
                "type": "session",
                "conversation_id": "conversation-safe",
                "turn_id": "turn-safe",
            },
            {
                "type": "event",
                "event_id": "cursor-safe",
                "data": {"type": "RUN_STARTED", "private": "must-not-be-reported"},
            },
            {
                "type": "event",
                "event_id": "terminal-cursor",
                "data": {"type": "RUN_FINISHED", "private": "must-not-be-reported"},
            },
        ]

        parsed = verifier.parse_finished_stream(
            "\n".join(json.dumps(record) for record in records)
        )

        self.assertEqual(
            parsed,
            {
                "conversation_id": "conversation-safe",
                "turn_id": "turn-safe",
                "last_event_id": "terminal-cursor",
                "terminal_event": "RUN_FINISHED",
            },
        )
        self.assertNotIn("private", json.dumps(parsed))

    def test_parse_cancelled_stream_requires_run_error_terminal(self) -> None:
        verifier = _load_module()
        records = [
            {
                "type": "session",
                "conversation_id": "conversation-safe",
                "turn_id": "turn-safe",
            },
            {
                "type": "event",
                "event_id": "cursor-safe",
                "data": {"type": "RUN_ERROR", "message": "redacted by parser"},
            },
        ]

        self.assertEqual(
            verifier.parse_cancelled_stream(
                "\n".join(json.dumps(record) for record in records)
            ),
            {
                "conversation_id": "conversation-safe",
                "turn_id": "turn-safe",
                "last_event_id": "cursor-safe",
                "terminal_event": "RUN_ERROR",
            },
        )
        with self.assertRaisesRegex(ValueError, "cancelled terminal event"):
            verifier.parse_cancelled_stream(
                "\n".join(json.dumps(record).replace("RUN_ERROR", "RUN_FINISHED") for record in records)
            )

    def test_parse_resumed_stream_accepts_missing_conversation_header_only_with_expected_context(self) -> None:
        verifier = _load_module()
        records = [
            {"type": "session", "conversation_id": "", "turn_id": "turn-safe"},
            {
                "type": "event",
                "event_id": "cursor-safe",
                "data": {"type": "RUN_FINISHED"},
            },
        ]

        self.assertEqual(
            verifier.parse_resumed_stream(
                "\n".join(json.dumps(record) for record in records),
                "conversation-safe",
                "turn-safe",
            ),
            {
                "conversation_id": "conversation-safe",
                "turn_id": "turn-safe",
                "last_event_id": "cursor-safe",
                "terminal_event": "RUN_FINISHED",
            },
        )
        with self.assertRaisesRegex(ValueError, "different turn"):
            verifier.parse_resumed_stream(
                "\n".join(json.dumps(record) for record in records),
                "conversation-safe",
                "other-turn",
            )

    def test_attachment_fixture_is_png_and_stream_must_identify_color_order(self) -> None:
        verifier = _load_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.png"
            verifier.write_attachment_fixture(path)
            payload = path.read_bytes()

        self.assertTrue(payload.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", payload[16:24])
        self.assertEqual((width, height), (96, 32))
        stream = "\n".join(
            (
                json.dumps(
                    {
                        "type": "event",
                        "event_id": "cursor-1",
                        "data": {
                            "type": "TEXT_MESSAGE_CONTENT",
                            "messageId": "message-1",
                            "delta": "I will inspect it.",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "event",
                        "event_id": "cursor-2",
                        "data": {
                            "type": "TEXT_MESSAGE_CONTENT",
                            "messageId": "message-2",
                            "delta": "red, green, blue",
                        },
                    }
                ),
            )
        )
        self.assertTrue(verifier.stream_text_matches(stream, "red, green, blue"))
        self.assertFalse(verifier.stream_text_matches(stream, "blue, green, red"))

    def test_parse_finished_stream_rejects_early_disconnect(self) -> None:
        verifier = _load_module()
        stream = "\n".join(
            (
                json.dumps(
                    {
                        "type": "session",
                        "conversation_id": "conversation-safe",
                        "turn_id": "turn-safe",
                    }
                ),
                json.dumps(
                    {
                        "type": "stream_error",
                        "last_event_id": "cursor-safe",
                    }
                ),
            )
        )

        with self.assertRaisesRegex(ValueError, "terminal event"):
            verifier.parse_finished_stream(stream)

    def test_parse_stream_checkpoint_returns_resume_safe_identifiers(self) -> None:
        verifier = _load_module()
        stream = "\n".join(
            (
                json.dumps(
                    {
                        "type": "session",
                        "conversation_id": "conversation-safe",
                        "turn_id": "turn-safe",
                    }
                ),
                json.dumps(
                    {
                        "type": "event",
                        "event_id": "cursor-safe",
                        "data": {"type": "RUN_STARTED"},
                    }
                ),
            )
        )

        self.assertEqual(
            verifier.parse_stream_checkpoint(stream),
            {
                "conversation_id": "conversation-safe",
                "turn_id": "turn-safe",
                "last_event_id": "cursor-safe",
            },
        )

    def test_parse_stream_checkpoint_rejects_terminal_or_unsafe_identifiers(self) -> None:
        verifier = _load_module()
        terminal = "\n".join(
            (
                json.dumps(
                    {
                        "type": "session",
                        "conversation_id": "conversation-safe",
                        "turn_id": "turn-safe",
                    }
                ),
                json.dumps(
                    {
                        "type": "event",
                        "event_id": "cursor-safe",
                        "data": {"type": "RUN_FINISHED"},
                    }
                ),
            )
        )
        with self.assertRaisesRegex(ValueError, "before interruption"):
            verifier.parse_stream_checkpoint(terminal)

        unsafe = terminal.replace("RUN_FINISHED", "RUN_STARTED").replace(
            "conversation-safe", "conversation/unsafe"
        )
        with self.assertRaisesRegex(ValueError, "invalid conversation identifier"):
            verifier.parse_stream_checkpoint(unsafe)

    def test_project_link_check_requires_compiled_profile_origin(self) -> None:
        verifier = _load_module()

        host = verifier.validate_project_link(
            {
                "profile": "dev",
                "project_id": "project-safe",
                "conversation_id": "conversation-safe",
                "deep_link": (
                    "https://dev.vivago.ai/agent/new-chat?"
                    "conversation_id=conversation-safe&project_id=project-safe"
                ),
            },
            "project-safe",
            "conversation-safe",
            "dev",
        )

        self.assertEqual(host, "dev.vivago.ai")
        with self.assertRaisesRegex(ValueError, "origin"):
            verifier.validate_project_link(
                {
                    "profile": "dev",
                    "project_id": "project-safe",
                    "conversation_id": "conversation-safe",
                    "deep_link": (
                        "https://vivago.ai/agent/new-chat?"
                        "conversation_id=conversation-safe&project_id=project-safe"
                    ),
                },
                "project-safe",
                "conversation-safe",
                "dev",
            )

        self.assertEqual(
            verifier.validate_project_link(
                {
                    "profile": "prod",
                    "project_id": "project-safe",
                    "conversation_id": "conversation-safe",
                    "deep_link": (
                        "https://vivago.ai/agent/new-chat?"
                        "conversation_id=conversation-safe&project_id=project-safe"
                    ),
                },
                "project-safe",
                "conversation-safe",
                "prod",
            ),
            "vivago.ai",
        )

    def test_production_report_removes_service_identifiers(self) -> None:
        verifier = _load_module()
        case = {
            "host": "codex",
            "plugin_version": "0.3.0-beta.1",
            "credential_backend": "keychain",
            "project_id": "project-secret",
            "conversation_id": "conversation-secret",
            "turn_id": "turn-secret",
            "last_event_id": "cursor-secret",
            "artifact_turn_id": "artifact-turn-secret",
            "artifact_bytes": 1024,
            "artifact_content_type": "image/png",
            "checks": {"attachment": "PASS", "artifact_preview_download": "PASS"},
        }

        sanitized = verifier.sanitize_production_case(case)

        self.assertEqual(
            sanitized,
            {
                "host": "codex",
                "plugin_version": "0.3.0-beta.1",
                "credential_backend": "keychain",
                "artifact_bytes": 1024,
                "artifact_content_type": "image/png",
                "checks": {"attachment": "PASS", "artifact_preview_download": "PASS"},
            },
        )
        self.assertNotRegex(json.dumps(sanitized), r"project-secret|conversation-secret|turn-secret|cursor-secret")

    def test_extract_image_artifact_requires_verified_succeeded_tool_result(self) -> None:
        verifier = _load_module()
        content_id = "j_0776c030-85cf-4f79-825d-449a41a05cde"
        stream = json.dumps(
            {
                "type": "event",
                "event_id": "cursor-safe",
                "data": {
                    "type": "TOOL_CALL_RESULT",
                    "toolCallName": "agent_gateway_wait_for_task",
                    "content": json.dumps(
                        {
                            "status": "succeeded",
                            "artifact_status": "verified",
                            "artifacts": {"images": [content_id]},
                        }
                    ),
                },
            }
        )

        self.assertEqual(verifier.extract_image_artifact(stream), content_id)
        with self.assertRaisesRegex(ValueError, "verified image artifact"):
            verifier.extract_image_artifact(
                stream.replace('\\"verified\\"', '\\"pending\\"')
            )

    def test_windows_launcher_keeps_batch_arguments_separate(self) -> None:
        verifier = _load_module()

        command = verifier.launcher_command(
            Path(r"C:\plugin path\vivago-agent.cmd"),
            "windows-arm64",
            ["--json", "project", "list", "--page-size", "1"],
        )

        self.assertEqual(
            command,
            [
                "cmd.exe",
                "/d",
                "/c",
                "call",
                r"C:\plugin path\vivago-agent.cmd",
                "--json",
                "project",
                "list",
                "--page-size",
                "1",
            ],
        )

    def test_safe_failure_detail_reports_code_without_sensitive_values(self) -> None:
        verifier = _load_module()

        self.assertEqual(
            verifier.safe_failure_detail(
                json.dumps(
                    {
                        "ok": False,
                        "error": {"code": "NETWORK_ERROR", "message": "request timed out"},
                    }
                )
            ),
            "NETWORK_ERROR: request timed out",
        )
        self.assertEqual(
            verifier.safe_failure_detail(
                json.dumps(
                    {
                        "ok": False,
                        "error": {"code": "BAD", "message": "ticket=secret-value"},
                    }
                )
            ),
            "structured error redacted",
        )

    def test_only_transport_failures_are_retryable_for_read_only_probe(self) -> None:
        verifier = _load_module()

        self.assertTrue(
            verifier.retryable_read_failure(
                ValueError("project list failed with exit 50: TRANSPORT_ERROR: request failed")
            )
        )
        self.assertFalse(
            verifier.retryable_read_failure(
                ValueError("project list failed with exit 20: INVALID_ARGUMENT")
            )
        )

    def test_project_name_avoids_gateway_sensitive_punctuation(self) -> None:
        verifier = _load_module()

        name = verifier.project_name(
            "claude-code",
            "windows-arm64",
            "local-attempt:9",
        )

        self.assertEqual(name, "E2E claude code windows arm64 local atte")
        self.assertLessEqual(len(name), 40)
        self.assertNotRegex(name, r"[^A-Za-z0-9 ]")


if __name__ == "__main__":
    unittest.main()
