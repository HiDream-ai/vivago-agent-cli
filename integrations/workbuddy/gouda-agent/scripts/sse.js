"use strict";

function parseData(parts) {
  const raw = parts.join("\n");
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

async function* decodeSSE(body) {
  if (!body || typeof body[Symbol.asyncIterator] !== "function") {
    throw new Error("SSE response body is unavailable");
  }
  const decoder = new TextDecoder("utf-8", { fatal: false });
  let buffer = "";
  let eventID = null;
  let eventName = "";
  let data = [];
  let hasField = false;

  function buildEvent() {
    const event = {
      event_id: eventID,
      event: eventName || "message",
      data: parseData(data),
    };
    eventID = null;
    eventName = "";
    data = [];
    hasField = false;
    return event;
  }

  function consumeLine(rawLine) {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (!line) {
      return hasField ? buildEvent() : null;
    }
    if (line.startsWith(":")) {
      return null;
    }
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    let value = colon < 0 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }
    if (field === "id") {
      eventID = value;
      hasField = true;
    } else if (field === "event") {
      eventName = value;
      hasField = true;
    } else if (field === "data") {
      data.push(value);
      hasField = true;
    }
    return null;
  }

  for await (const chunk of body) {
    buffer += decoder.decode(chunk, { stream: true });
    while (true) {
      const newline = buffer.indexOf("\n");
      if (newline < 0) {
        break;
      }
      const line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      const event = consumeLine(line);
      if (event) {
        yield event;
      }
    }
  }
  buffer += decoder.decode();
  if (buffer) {
    const event = consumeLine(buffer);
    if (event) {
      yield event;
    }
  }
  if (hasField) {
    yield buildEvent();
  }
}

function terminalType(event) {
  const candidate =
    event && event.data && typeof event.data === "object" && event.data.type
      ? event.data.type
      : event && event.event;
  return candidate === "RUN_FINISHED" || candidate === "RUN_ERROR" ? candidate : "";
}

module.exports = { decodeSSE, terminalType };
