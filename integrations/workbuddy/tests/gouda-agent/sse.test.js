"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { decodeSSE, terminalType } = require("../../gouda-agent/scripts/sse");

function streamFromChunks(chunks) {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(Buffer.from(chunk));
      }
      controller.close();
    },
  });
}

test("SSE decoder handles chunk boundaries, CRLF, comments, and multiline JSON", async () => {
  const events = [];
  for await (const event of decodeSSE(
    streamFromChunks([
      ": keepalive\r\nid: event-1\r\nevent: message\r\ndata: {\"type\":\r\n",
      "data: \"TEXT_MESSAGE_CONTENT\",\"delta\":\"hello\"}\r\n\r\n",
      "data: plain text\n\n",
    ]),
  )) {
    events.push(event);
  }
  assert.deepEqual(events, [
    {
      event_id: "event-1",
      event: "message",
      data: { type: "TEXT_MESSAGE_CONTENT", delta: "hello" },
    },
    { event_id: null, event: "message", data: "plain text" },
  ]);
});

test("terminal type recognizes only RUN_FINISHED and RUN_ERROR", () => {
  assert.equal(terminalType({ event: "message", data: { type: "RUN_FINISHED" } }), "RUN_FINISHED");
  assert.equal(terminalType({ event: "RUN_ERROR", data: {} }), "RUN_ERROR");
  assert.equal(terminalType({ event: "message", data: { type: "RUN_STARTED" } }), "");
});
