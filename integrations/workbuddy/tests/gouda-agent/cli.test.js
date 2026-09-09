"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { run } = require("../../gouda-agent/scripts/gouda-agent");

function sink() {
  let value = "";
  return {
    write(chunk) {
      value += String(chunk);
    },
    value() {
      return value;
    },
  };
}

function eventBody(events) {
  return new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(
          Buffer.from(`id: ${event.id}\ndata: ${JSON.stringify(event.data)}\n\n`),
        );
      }
      controller.close();
    },
  });
}

test("doctor reports the Node runtime without initializing network helpers", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = undefined;
  try {
    const stdout = sink();
    const exitCode = await run(["doctor"], { stdout, stderr: sink() });
    assert.equal(exitCode === 0 || exitCode === 40, true);
    assert.equal(JSON.parse(stdout.value()).data.node_version, process.versions.node);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("artifact url command emits one JSON envelope with the domestic prefix", async () => {
  const stdout = sink();
  const stderr = sink();
  const exitCode = await run(
    ["artifact", "url", "--media-type", "video", "--content-id", "result-1"],
    { stdout, stderr },
  );
  assert.equal(exitCode, 0);
  assert.deepEqual(JSON.parse(stdout.value()), {
    ok: true,
    data: { url: "https://media-cdn.hidreamai.com/result-1.mp4" },
    error: null,
  });
  assert.equal(stderr.value(), "");
});

test("project link uses the domestic top-level new-chat route", async () => {
  const stdout = sink();
  const stderr = sink();
  const exitCode = await run(
    [
      "project",
      "link",
      "--project-id",
      "project-1",
      "--conversation-id",
      "conversation-1",
    ],
    { stdout, stderr },
  );
  assert.equal(exitCode, 0);
  assert.deepEqual(JSON.parse(stdout.value()).data, {
    project_id: "project-1",
    conversation_id: "conversation-1",
    deep_link:
      "https://goudaai.com/new-chat?project_id=project-1&conversation_id=conversation-1",
    profile: "domestic-prod",
  });
  assert.equal(stderr.value(), "");
});

test("ask emits JSONL, stores only identifiers, and records terminal completion", async () => {
  const stdout = sink();
  const stderr = sink();
  const writes = [];
  const fakeClient = {
    async ask(prompt, options) {
      assert.equal(prompt, "Create one image");
      assert.equal(options.projectID, "project-1");
      return {
        conversationID: "conversation-1",
        turnID: "turn-1",
        body: eventBody([
          { id: "event-1", data: { type: "RUN_STARTED" } },
          { id: "event-2", data: { type: "RUN_FINISHED" } },
        ]),
      };
    },
  };
  const stateStore = {
    async upsert(value) {
      writes.push(value);
      return value;
    },
  };
  const exitCode = await run(
    ["ask", "--project-id", "project-1", "--prompt", "Create one image"],
    { stdout, stderr, client: fakeClient, stateStore },
  );
  assert.equal(exitCode, 0);
  const records = stdout.value().trim().split("\n").map(JSON.parse);
  assert.equal(records[0].type, "session");
  assert.equal(records[0].conversation_id, "conversation-1");
  assert.equal(records.at(-1).data.type, "RUN_FINISHED");
  assert.equal(writes[0].project_id, "project-1");
  assert.equal(writes.at(-1).last_event_id, "event-2");
  assert.equal(writes.at(-1).status, "finished");
  assert.equal(JSON.stringify(writes).includes("Create one image"), false);
  assert.equal(stderr.value(), "");
});

test("ask validates required arguments before inspecting or uploading attachments", async () => {
  const stdout = sink();
  let validationCalls = 0;
  let uploadCalls = 0;
  const exitCode = await run(
    ["ask", "--project-id", "project-1", "--file", "/tmp/authorized.png"],
    {
      stdout,
      stderr: sink(),
      validateAttachmentsImpl: async () => {
        validationCalls += 1;
        return [];
      },
      uploadAttachmentImpl: async () => {
        uploadCalls += 1;
      },
    },
  );
  assert.equal(exitCode, 10);
  assert.equal(validationCalls, 0);
  assert.equal(uploadCalls, 0);
  assert.equal(JSON.parse(stdout.value()).error.code, "INVALID_ARGUMENT");
});

test("an early stream end emits recoverable state and exit 50", async () => {
  const stdout = sink();
  const stderr = sink();
  const writes = [];
  const exitCode = await run(
    ["resume", "--turn-id", "turn-1", "--last-event-id", "event-1"],
    {
      stdout,
      stderr,
      client: {
        async resume() {
          return {
            conversationID: "conversation-1",
            turnID: "turn-1",
            body: eventBody([{ id: "event-2", data: { type: "RUN_STARTED" } }]),
          };
        },
      },
      stateStore: {
        async show() {
          return { project_id: "project-1", conversation_id: "conversation-1" };
        },
        async upsert(value) {
          writes.push(value);
        },
      },
    },
  );
  assert.equal(exitCode, 50);
  const records = stdout.value().trim().split("\n").map(JSON.parse);
  assert.equal(records.at(-1).type, "stream_error");
  assert.equal(records.at(-1).last_event_id, "event-2");
  assert.equal(writes.at(-1).status, "interrupted");
});

test("auth status output contains status only", async () => {
  const stdout = sink();
  const exitCode = await run(["auth", "status"], {
    stdout,
    stderr: sink(),
    authProvider: {
      async status() {
        return { logged_in: true, backend: "file", needs_refresh: false };
      },
    },
  });
  assert.equal(exitCode, 0);
  assert.deepEqual(JSON.parse(stdout.value()).data, {
    logged_in: true,
    backend: "file",
    needs_refresh: false,
  });
});

test("cancel is a top-level command and forwards both identifiers", async () => {
  const stdout = sink();
  let captured;
  const exitCode = await run(
    [
      "cancel",
      "--conversation-id",
      "conversation-1",
      "--turn-id",
      "turn-1",
    ],
    {
      stdout,
      stderr: sink(),
      client: {
        async cancel(conversationID, turnID) {
          captured = { conversationID, turnID };
          return { code: 0 };
        },
      },
    },
  );
  assert.equal(exitCode, 0);
  assert.deepEqual(captured, {
    conversationID: "conversation-1",
    turnID: "turn-1",
  });
});

test("project assets exposes account asset recovery with an optional offset", async () => {
  const stdout = sink();
  let captured;
  const exitCode = await run(
    ["project", "assets", "--offset", "4", "--page-size", "25"],
    {
      stdout,
      stderr: sink(),
      client: {
        async listProjectAssets(offset, pageSize) {
          captured = { offset, pageSize };
          return { code: 0, data: { list: [] } };
        },
      },
    },
  );
  assert.equal(exitCode, 0);
  assert.deepEqual(captured, { offset: 4, pageSize: 25 });
  assert.deepEqual(JSON.parse(stdout.value()).data, { code: 0, data: { list: [] } });
});

test("artifact preview and download route through the domestic artifact downloader", async () => {
  const calls = [];
  const artifactDownloader = {
    async preview(mediaType, contentID) {
      calls.push({ command: "preview", mediaType, contentID });
      return { path: "/tmp/preview.jpg", bytes: 3, content_type: "image/jpeg" };
    },
    async download(mediaType, contentID, outputPath) {
      calls.push({ command: "download", mediaType, contentID, outputPath });
      return { path: outputPath, bytes: 4, content_type: "video/mp4" };
    },
  };

  const previewOutput = sink();
  assert.equal(
    await run(
      ["artifact", "preview", "--media-type", "image", "--content-id", "p_demo"],
      { stdout: previewOutput, stderr: sink(), artifactDownloader },
    ),
    0,
  );
  assert.equal(JSON.parse(previewOutput.value()).data.path, "/tmp/preview.jpg");

  const downloadOutput = sink();
  assert.equal(
    await run(
      [
        "artifact",
        "download",
        "--media-type",
        "video",
        "--content-id",
        "result.mp4",
        "--output",
        "/tmp/result.mp4",
      ],
      { stdout: downloadOutput, stderr: sink(), artifactDownloader },
    ),
    0,
  );
  assert.deepEqual(calls, [
    { command: "preview", mediaType: "image", contentID: "p_demo" },
    {
      command: "download",
      mediaType: "video",
      contentID: "result.mp4",
      outputPath: "/tmp/result.mp4",
    },
  ]);
});

test("HTTP 401 maps to the login-required exit code without exposing a response body", async () => {
  const stdout = sink();
  const error = Object.assign(new Error("Gouda Agent request failed with HTTP 401"), {
    code: "HTTP_ERROR",
    statusCode: 401,
  });
  const exitCode = await run(["project", "create", "--name", "Rejected"], {
    stdout,
    stderr: sink(),
    client: {
      async createProject() {
        throw error;
      },
    },
  });
  assert.equal(exitCode, 20);
  assert.equal(stdout.value().includes("ticket"), false);
});
