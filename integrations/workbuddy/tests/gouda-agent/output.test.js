"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { redact } = require("../../gouda-agent/scripts/output");

test("output redaction removes credential fields and signed URLs recursively", () => {
  assert.deepEqual(
    redact({
      ticket: "ticket-value",
      nested: {
        Authorization: "Bearer value",
        AccessKeySecret: "access-secret",
        url: "https://bucket.example/file?OSSAccessKeyId=value&Signature=value",
      },
      safe: "https://media-cdn.hidreamai.com/result.mp4",
    }),
    {
      ticket: "[REDACTED]",
      nested: {
        Authorization: "[REDACTED]",
        AccessKeySecret: "[REDACTED]",
        url: "[REDACTED_URL]",
      },
      safe: "https://media-cdn.hidreamai.com/result.mp4",
    },
  );
});
