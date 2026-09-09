"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { GoudaClient } = require("../../gouda-agent/scripts/client");

function jsonResponse(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status || 200,
    headers: { "content-type": "application/json", ...(init.headers || {}) },
  });
}

test("project create uses domestic v1 endpoint and project version v3", async () => {
  let captured;
  const client = new GoudaClient({
    tokenProvider: async () => "unit-ticket",
    fetchImpl: async (url, options) => {
      captured = { url, options };
      return jsonResponse({ code: 0, data: { project_id: "project-1" } });
    },
  });

  const result = await client.createProject("WorkBuddy task");
  assert.equal(captured.url, "https://goudaai.com/api/agent/v1/project/create");
  assert.equal(captured.options.method, "POST");
  assert.deepEqual(JSON.parse(captured.options.body), {
    name: "WorkBuddy task",
    version: "v3",
  });
  assert.equal(captured.options.headers.Authorization, "Bearer unit-ticket");
  assert.equal(captured.options.headers["X-Source"], "cli");
  assert.equal(captured.options.headers["X-Client-Platform"], "web");
  assert.match(captured.options.headers["User-Agent"], /^gouda-agent-workbuddy\//);
  assert.equal(result.data.project_id, "project-1");
});

test("project assets uses the shared domestic asset-list contract", async () => {
  let captured;
  const client = new GoudaClient({
    tokenProvider: async () => "unit-ticket",
    fetchImpl: async (url, options) => {
      captured = { url, options };
      return jsonResponse({ code: 0, data: { list: [], offset: 7 } });
    },
  });

  const result = await client.listProjectAssets(3, 25);
  assert.equal(captured.url, "https://goudaai.com/api/agent/v1/project_asset_list");
  assert.deepEqual(JSON.parse(captured.options.body), { offset: 3, page_size: 25 });
  assert.equal(result.data.offset, 7);
});

test("domestic OSS credentials use oss_key and image/media category without query", async () => {
  const urls = [];
  const client = new GoudaClient({
    tokenProvider: async () => "unit-ticket",
    fetchImpl: async (url) => {
      urls.push(url);
      return jsonResponse({ code: 0, result: { marker: true } });
    },
  });

  await client.getOSSCredentials("image");
  await client.getOSSCredentials("media");
  assert.deepEqual(urls, [
    "https://goudaai.com/prod-api/user/oss_key/image",
    "https://goudaai.com/prod-api/user/oss_key/media",
  ]);
  assert.throws(() => client.getOSSCredentials("hidreamai-image"), /bucket/i);
});

test("API errors are structured and do not expose response bodies", async () => {
  const client = new GoudaClient({
    tokenProvider: async () => "unit-ticket",
    fetchImpl: async () =>
      jsonResponse(
        { code: 1007, message: "rejected unit-ticket", secret: "do-not-print" },
        { status: 401 },
      ),
  });

  await assert.rejects(
    () => client.createProject("Rejected"),
    (error) => {
      assert.equal(error.code, "HTTP_ERROR");
      assert.equal(error.statusCode, 401);
      assert.equal(error.message.includes("unit-ticket"), false);
      assert.equal(error.message.includes("do-not-print"), false);
      return true;
    },
  );
});

test("ask starts the domestic SSE conversation contract", async () => {
  let captured;
  const client = new GoudaClient({
    tokenProvider: async () => "unit-ticket",
    fetchImpl: async (url, options) => {
      if (url.endsWith("/api/agent/v1/project/detail")) {
        return jsonResponse({ code: 0, data: { conversations: [] } });
      }
      captured = { url, options };
      return new Response("data: {\"type\":\"RUN_FINISHED\"}\n\n", {
        status: 200,
        headers: {
          "content-type": "text/event-stream",
          "x-vivago-conversation-id": "conversation-1",
          "x-vivago-turn-id": "turn-1",
        },
      });
    },
  });

  const stream = await client.ask("Create one image", {
    projectID: "project-1",
    imageSearchEnabled: true,
  });
  const body = JSON.parse(captured.options.body);
  assert.equal(captured.url, "https://goudaai.com/api/agent/v2/conversation/chat");
  assert.equal(captured.options.headers.Accept, "text/event-stream");
  assert.equal(body.projectId, "project-1");
  assert.equal(body.threadId, "");
  assert.equal(body.imageSearchEnabled, true);
  assert.equal(body.messages[0].role, "user");
  assert.deepEqual(body.messages[0].content, [
    { type: "text", text: "Create one image" },
  ]);
  assert.equal(stream.conversationID, "conversation-1");
  assert.equal(stream.turnID, "turn-1");
});

test("resume sends no prompt and preserves the supplied turn when response omits it", async () => {
  let captured;
  const client = new GoudaClient({
    tokenProvider: async () => "unit-ticket",
    fetchImpl: async (url, options) => {
      captured = { url, options };
      return new Response("data: {\"type\":\"RUN_FINISHED\"}\n\n", {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      });
    },
  });
  const stream = await client.resume("turn-original", "event-9");
  const body = JSON.parse(captured.options.body);
  assert.deepEqual(body.messages, []);
  assert.equal(body.turnId, "turn-original");
  assert.equal(body.lastEventId, "event-9");
  assert.equal(stream.turnID, "turn-original");
});

test("ask requires exactly one project or conversation identifier", async () => {
  const client = new GoudaClient({
    tokenProvider: async () => "unit-ticket",
    fetchImpl: async () => {
      throw new Error("must not be called");
    },
  });
  await assert.rejects(() => client.ask("hello", {}), /exactly one/i);
  await assert.rejects(
    () =>
      client.ask("hello", {
        projectID: "project-1",
        conversationID: "conversation-1",
      }),
    /exactly one/i,
  );
});
