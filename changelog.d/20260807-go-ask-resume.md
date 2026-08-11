# Added

- Add Go `ask` and `resume` JSONL commands on the Web v2 SSE endpoint.
- Preflight project conversations before starting a turn, reuse the only existing conversation, and reject ambiguous project bindings.
- Resume only the original turn with `turn_id + last_event_id`; never resubmit the original prompt automatically.

# Security

- Generate message IDs with cryptographically secure UUID v4 values.
- Redact low-level SSE decoder errors from machine-readable output while preserving the safe resume cursor.
