"use strict";

const crypto = require("node:crypto");
const http = require("node:http");
const { spawn } = require("node:child_process");

const { PROFILE } = require("./config");

const MAX_CALLBACK_BYTES = 64 * 1024;

function buildLoginURL(port, state) {
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("callback port is out of range");
  }
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(state)) {
    throw new Error("state must be 32 to 128 URL-safe characters");
  }
  const url = new URL(PROFILE.loginURL);
  url.search = new URLSearchParams({
    client: "vivago-agent-cli",
    callback_port: String(port),
    state,
  }).toString();
  return url.toString();
}

function equalState(actual, expected) {
  const left = Buffer.from(String(actual || ""));
  const right = Buffer.from(String(expected || ""));
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}

function isLoopback(address) {
  return (
    address === "127.0.0.1" ||
    address === "::1" ||
    String(address || "").startsWith("::ffff:127.")
  );
}

async function defaultOpenURL(url) {
  let command;
  let args;
  if (process.platform === "darwin") {
    command = "open";
    args = [url];
  } else if (process.platform === "win32") {
    command = "rundll32";
    args = ["url.dll,FileProtocolHandler", url];
  } else {
    command = "xdg-open";
    args = [url];
  }
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      detached: true,
      stdio: "ignore",
      windowsHide: true,
    });
    child.once("error", () => resolve(false));
    child.once("spawn", () => {
      child.unref();
      resolve(true);
    });
  });
}

async function login({
  store,
  openURL = defaultOpenURL,
  onManualURL,
  timeoutMs = 5 * 60 * 1000,
} = {}) {
  if (!store || typeof store.save !== "function") {
    throw new Error("credential store is required");
  }
  const state = crypto.randomBytes(32).toString("base64url");
  let resolveCallback;
  let rejectCallback;
  const callback = new Promise((resolve, reject) => {
    resolveCallback = resolve;
    rejectCallback = reject;
  });
  let consumed = false;
  const server = http.createServer((request, response) => {
    if (!isLoopback(request.socket.remoteAddress)) {
      response.writeHead(403).end("callback must come from loopback");
      return;
    }
    if (request.method !== "POST" || request.url !== "/callback") {
      response.writeHead(404).end("invalid callback request");
      return;
    }
    const contentType = String(request.headers["content-type"] || "");
    if (!contentType.toLowerCase().startsWith("application/x-www-form-urlencoded")) {
      response.writeHead(400).end("invalid callback form");
      return;
    }
    let size = 0;
    const chunks = [];
    request.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_CALLBACK_BYTES) {
        response.writeHead(413).end("callback form is too large");
        request.destroy();
        return;
      }
      chunks.push(chunk);
    });
    request.on("end", () => {
      if (size > MAX_CALLBACK_BYTES) {
        return;
      }
      const form = new URLSearchParams(Buffer.concat(chunks).toString("utf8"));
      const ticket = String(form.get("ticket") || "").trim();
      const refreshToken = String(form.get("refresh_token") || "").trim();
      const returnedState = form.get("state");
      if (!ticket || !refreshToken || !returnedState || !equalState(returnedState, state)) {
        response.writeHead(400).end("invalid callback form");
        return;
      }
      if (consumed) {
        response.writeHead(409).end("callback already used");
        return;
      }
      consumed = true;
      response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      response.end("<!doctype html><title>Gouda Agent</title><p>Login completed.</p>");
      resolveCallback({ ticket, refresh_token: refreshToken });
    });
    request.on("error", rejectCallback);
  });

  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  const url = buildLoginURL(address.port, state);
  let opened = false;
  try {
    opened = (await openURL(url)) !== false;
  } catch {
    opened = false;
  }
  if (!opened && typeof onManualURL === "function") {
    onManualURL(url);
  }

  let timer;
  try {
    const credentials = await Promise.race([
      callback,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("login timed out")), timeoutMs);
      }),
    ]);
    await store.save(credentials);
    return { logged_in: true, backend: store.backend || "file" };
  } finally {
    clearTimeout(timer);
    await new Promise((resolve) => server.close(resolve));
  }
}

function ticketNeedsRefresh(ticket, nowMs = Date.now(), skewSeconds = 300) {
  try {
    const parts = String(ticket || "").split(".");
    if (parts.length !== 3) {
      return true;
    }
    const payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8"));
    return !Number.isFinite(payload.exp) || payload.exp <= nowMs / 1000 + skewSeconds;
  } catch {
    return true;
  }
}

async function refreshTicket(refreshToken, { fetchImpl = globalThis.fetch } = {}) {
  if (!String(refreshToken || "").trim()) {
    throw new Error("refresh token is required");
  }
  let response;
  try {
    response = await fetchImpl(PROFILE.apiBaseURL + PROFILE.refreshPath, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Refresh-Token": refreshToken,
        "User-Agent": `gouda-agent-workbuddy/${PROFILE.skillVersion}`,
      },
      redirect: "error",
      signal: AbortSignal.timeout(30_000),
    });
  } catch {
    const error = new Error("token refresh failed");
    error.code = "NETWORK_ERROR";
    throw error;
  }
  if (!response.ok) {
    const error = new Error(`token refresh failed with HTTP ${response.status}`);
    error.code = response.status === 400 || response.status === 401 || response.status === 403
      ? "LOGIN_REQUIRED"
      : "REFRESH_ERROR";
    throw error;
  }
  let payload;
  try {
    payload = JSON.parse(await response.text());
  } catch {
    const error = new Error("token refresh response is invalid");
    error.code = "PROTOCOL_ERROR";
    throw error;
  }
  if (payload.code !== 0 || typeof payload.result?.token !== "string" || !payload.result.token) {
    const error = new Error("token refresh was rejected");
    error.code = "LOGIN_REQUIRED";
    throw error;
  }
  return payload.result.token;
}

class AuthProvider {
  constructor(store, { fetchImpl = globalThis.fetch, now = () => Date.now() } = {}) {
    this.store = store;
    this.fetchImpl = fetchImpl;
    this.now = now;
  }

  async status() {
    try {
      const credentials = await this.store.load();
      return {
        logged_in: true,
        backend: this.store.backend,
        needs_refresh: ticketNeedsRefresh(credentials.ticket, this.now()),
      };
    } catch (error) {
      if (error && error.code === "LOGIN_REQUIRED") {
        return { logged_in: false, backend: this.store.backend, needs_refresh: false };
      }
      throw error;
    }
  }

  async accessToken() {
    const credentials = await this.store.load();
    if (!ticketNeedsRefresh(credentials.ticket, this.now())) {
      return credentials.ticket;
    }
    return this.refresh(credentials);
  }

  async forceRefresh() {
    return this.refresh(await this.store.load());
  }

  async refresh(credentials) {
    try {
      const ticket = await refreshTicket(credentials.refresh_token, {
        fetchImpl: this.fetchImpl,
      });
      await this.store.save({ ...credentials, ticket });
      return ticket;
    } catch (error) {
      if (error && error.code === "LOGIN_REQUIRED") {
        await this.store.delete();
      }
      throw error;
    }
  }
}

module.exports = {
  AuthProvider,
  buildLoginURL,
  defaultOpenURL,
  equalState,
  isLoopback,
  login,
  refreshTicket,
  ticketNeedsRefresh,
};
