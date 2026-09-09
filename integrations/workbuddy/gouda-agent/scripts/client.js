"use strict";

const crypto = require("node:crypto");
const os = require("node:os");

const { PROFILE } = require("./config");

const MAX_JSON_BYTES = 1024 * 1024;

class GoudaError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = "GoudaError";
    this.code = options.code || "REQUEST_ERROR";
    this.statusCode = options.statusCode || 0;
    this.serverCode = options.serverCode;
  }
}

function requestHeaders(ticket) {
  return {
    Authorization: `Bearer ${ticket}`,
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-Source": "cli",
    "X-Client-Platform": "web",
    "X-Client-Version": PROFILE.skillVersion,
    "User-Agent": `gouda-agent-workbuddy/${PROFILE.skillVersion} (${os.platform()}; ${os.arch()})`,
  };
}

async function decodeJSONResponse(response) {
  const text = await response.text();
  if (Buffer.byteLength(text, "utf8") > MAX_JSON_BYTES) {
    throw new GoudaError("Gouda Agent response exceeds the size limit", {
      code: "PROTOCOL_ERROR",
    });
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new GoudaError("Gouda Agent returned invalid JSON", {
      code: "PROTOCOL_ERROR",
    });
  }
}

class GoudaClient {
  constructor({ tokenProvider, fetchImpl = globalThis.fetch } = {}) {
    if (typeof tokenProvider !== "function") {
      throw new Error("token provider is required");
    }
    if (typeof fetchImpl !== "function") {
      throw new Error("fetch implementation is required");
    }
    this.tokenProvider = tokenProvider;
    this.fetchImpl = fetchImpl;
  }

  async requestJSON(method, path, body) {
    const ticket = await this.tokenProvider();
    const options = {
      method,
      headers: requestHeaders(ticket),
      redirect: "error",
      signal: AbortSignal.timeout(60_000),
    };
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }
    let response;
    try {
      response = await this.fetchImpl(PROFILE.apiBaseURL + path, options);
    } catch {
      throw new GoudaError("Gouda Agent request failed", { code: "NETWORK_ERROR" });
    }
    if (!response.ok) {
      throw new GoudaError(`Gouda Agent request failed with HTTP ${response.status}`, {
        code: "HTTP_ERROR",
        statusCode: response.status,
      });
    }
    const decoded = await decodeJSONResponse(response);
    if (decoded.code !== undefined && decoded.code !== 0 && decoded.code !== "0") {
      throw new GoudaError("Gouda Agent rejected the request", {
        code: "BUSINESS_ERROR",
        serverCode: decoded.code,
      });
    }
    return decoded;
  }

  createProject(name) {
    const normalized = String(name || "").trim();
    if (!normalized) {
      throw new GoudaError("project name is required", { code: "INVALID_ARGUMENT" });
    }
    return this.requestJSON("POST", "/api/agent/v1/project/create", {
      name: normalized,
      version: PROFILE.projectVersion,
    });
  }

  listProjects(pageNumber = 0, pageSize = 20) {
    return this.requestJSON("POST", "/api/agent/v1/project/list", {
      page_no: pageNumber,
      page_size: pageSize,
    });
  }

  projectDetail(projectID) {
    return this.requestJSON("POST", "/api/agent/v1/project/detail", {
      project_id: String(projectID || "").trim(),
    });
  }

  listProjectAssets(offset = null, pageSize = 20) {
    return this.requestJSON("POST", "/api/agent/v1/project_asset_list", {
      offset,
      page_size: pageSize,
    });
  }

  cancel(conversationID, turnID) {
    return this.requestJSON("POST", "/api/agent/v2/conversation/cancel", {
      conversation_id: String(conversationID || "").trim(),
      turn_id: String(turnID || "").trim(),
    });
  }

  history(conversationID, pageNumber = 0, pageSize = 20) {
    return this.requestJSON("POST", "/api/agent/v2/conversation/history", {
      conversation_id: String(conversationID || "").trim(),
      page_no: pageNumber,
      page_size: pageSize,
    });
  }

  getOSSCredentials(bucket) {
    if (bucket !== "image" && bucket !== "media") {
      throw new GoudaError("OSS bucket category must be image or media", {
        code: "INVALID_ARGUMENT",
      });
    }
    return this.requestJSON("GET", `${PROFILE.ossCredentialPath}/${bucket}`);
  }

  async projectConversationID(projectID) {
    const response = await this.projectDetail(projectID);
    const conversations = response && response.data && response.data.conversations;
    if (!Array.isArray(conversations)) {
      throw new GoudaError("project detail response is missing conversations", {
        code: "PROTOCOL_ERROR",
      });
    }
    const identifiers = conversations
      .filter((value) => typeof value === "string" && value.trim())
      .map((value) => value.trim());
    if (identifiers.length > 1) {
      throw new GoudaError("project already has multiple conversations", {
        code: "PROJECT_CONVERSATION_CONFLICT",
      });
    }
    return identifiers[0] || "";
  }

  async ask(prompt, {
    projectID = "",
    conversationID = "",
    imageSearchEnabled = false,
    attachments = [],
  } = {}) {
    const normalizedPrompt = String(prompt || "").trim();
    const normalizedProjectID = String(projectID || "").trim();
    let normalizedConversationID = String(conversationID || "").trim();
    if (!normalizedPrompt) {
      throw new GoudaError("prompt is required", { code: "INVALID_ARGUMENT" });
    }
    if (Boolean(normalizedProjectID) === Boolean(normalizedConversationID)) {
      throw new GoudaError(
        "exactly one of project ID or conversation ID is required",
        { code: "INVALID_ARGUMENT" },
      );
    }
    if (normalizedProjectID) {
      normalizedConversationID = await this.projectConversationID(normalizedProjectID);
    }
    const content = [{ type: "text", text: normalizedPrompt }];
    for (const item of attachments) {
      content.push({
        type: item.mediaType,
        source: { type: "url", value: item.ossKey },
        name: item.name,
      });
    }
    const body = {
      threadId: normalizedConversationID,
      runId: "",
      state: {},
      messages: [
        {
          id: crypto.randomUUID(),
          role: "user",
          content,
        },
      ],
      tools: [],
      context: [],
      forwardedProps: {},
    };
    if (!normalizedConversationID) {
      body.projectId = normalizedProjectID;
    }
    if (imageSearchEnabled) {
      body.imageSearchEnabled = true;
    }
    return this.startChat(body);
  }

  async resume(turnID, lastEventID = "") {
    const normalizedTurnID = String(turnID || "").trim();
    if (!normalizedTurnID) {
      throw new GoudaError("turn ID is required", { code: "INVALID_ARGUMENT" });
    }
    const body = {
      threadId: "",
      runId: "",
      state: {},
      messages: [],
      tools: [],
      context: [],
      forwardedProps: {},
      turnId: normalizedTurnID,
    };
    if (String(lastEventID || "").trim()) {
      body.lastEventId = String(lastEventID).trim();
    }
    const stream = await this.startChat(body);
    if (!stream.turnID) {
      stream.turnID = normalizedTurnID;
    }
    return stream;
  }

  async startChat(body) {
    const ticket = await this.tokenProvider();
    const headers = requestHeaders(ticket);
    headers.Accept = "text/event-stream";
    let response;
    try {
      response = await this.fetchImpl(
        PROFILE.apiBaseURL + "/api/agent/v2/conversation/chat",
        {
          method: "POST",
          headers,
          body: JSON.stringify(body),
          redirect: "error",
        },
      );
    } catch {
      throw new GoudaError("Gouda Agent stream request failed", {
        code: "NETWORK_ERROR",
      });
    }
    if (!response.ok) {
      throw new GoudaError(`Gouda Agent stream failed with HTTP ${response.status}`, {
        code: "HTTP_ERROR",
        statusCode: response.status,
      });
    }
    if (!response.body) {
      throw new GoudaError("Gouda Agent stream body is unavailable", {
        code: "PROTOCOL_ERROR",
      });
    }
    return {
      conversationID: response.headers.get("x-vivago-conversation-id") || "",
      turnID: response.headers.get("x-vivago-turn-id") || "",
      body: response.body,
    };
  }
}

module.exports = {
  GoudaClient,
  GoudaError,
  requestHeaders,
  decodeJSONResponse,
};
