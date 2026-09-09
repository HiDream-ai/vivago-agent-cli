"use strict";

const SENSITIVE_KEY = /^(?:authorization|cookie|set-cookie|ticket|refresh[_-]?token|accesskeyid|accesskeysecret|securitytoken)$/i;
const SIGNED_URL = /[?&](?:x-amz-signature|signature|ossaccesskeyid|security-token)=/i;

function redact(value, seen = new WeakSet()) {
  if (typeof value === "string") {
    return SIGNED_URL.test(value) ? "[REDACTED_URL]" : value;
  }
  if (!value || typeof value !== "object") {
    return value;
  }
  if (seen.has(value)) {
    return "[CIRCULAR]";
  }
  seen.add(value);
  if (Array.isArray(value)) {
    return value.map((item) => redact(item, seen));
  }
  const result = {};
  for (const [key, item] of Object.entries(value)) {
    result[key] = SENSITIVE_KEY.test(key) ? "[REDACTED]" : redact(item, seen);
  }
  return result;
}

function writeRecord(stream, value) {
  stream.write(JSON.stringify(redact(value)) + "\n");
}

function writeSuccess(stream, data) {
  writeRecord(stream, { ok: true, data, error: null });
}

function writeFailure(stream, error) {
  writeRecord(stream, {
    ok: false,
    data: null,
    error: {
      code: error && error.code ? String(error.code) : "INTERNAL_ERROR",
      message: error && error.message ? String(error.message) : "operation failed",
      ...(error && error.statusCode ? { status_code: error.statusCode } : {}),
      ...(error && error.serverCode !== undefined
        ? { server_code: error.serverCode }
        : {}),
    },
  });
}

module.exports = { redact, writeFailure, writeRecord, writeSuccess };
