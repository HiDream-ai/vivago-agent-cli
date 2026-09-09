"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  AuthProvider,
  buildLoginURL,
  login,
  refreshTicket,
  ticketNeedsRefresh,
} = require("../../gouda-agent/scripts/auth");

function jwtWithExpiry(exp) {
  const encode = (value) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "none" })}.${encode({ exp })}.signature`;
}

test("login URL uses the verified domestic callback contract", () => {
  const state = "a".repeat(43);
  const parsed = new URL(buildLoginURL(43123, state));
  assert.equal(parsed.origin + parsed.pathname, "https://goudaai.com/login");
  assert.equal(parsed.searchParams.get("client"), "vivago-agent-cli");
  assert.equal(parsed.searchParams.get("callback_port"), "43123");
  assert.equal(parsed.searchParams.get("state"), state);
  assert.equal(parsed.searchParams.has("callback_url"), false);
});

test("loopback login accepts one valid form callback without returning secrets", async () => {
  const saved = [];
  let loginURL;
  const store = {
    async save(credentials) {
      saved.push(credentials);
    },
  };
  const result = await login({
    store,
    timeoutMs: 2_000,
    openURL: async (url) => {
      loginURL = new URL(url);
      const response = await fetch(
        `http://127.0.0.1:${loginURL.searchParams.get("callback_port")}/callback`,
        {
          method: "POST",
          headers: { "content-type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            ticket: "callback-ticket",
            refresh_token: "callback-refresh",
            state: loginURL.searchParams.get("state"),
          }),
        },
      );
      assert.equal(response.status, 200);
      assert.equal((await response.text()).includes("callback-ticket"), false);
    },
  });

  assert.equal(loginURL.origin + loginURL.pathname, "https://goudaai.com/login");
  assert.deepEqual(saved, [
    { ticket: "callback-ticket", refresh_token: "callback-refresh" },
  ]);
  assert.deepEqual(result, { logged_in: true, backend: "file" });
  assert.equal(JSON.stringify(result).includes("callback-ticket"), false);
});

test("loopback login rejects the wrong state and times out safely", async () => {
  let callbackStatus;
  await assert.rejects(
    () =>
      login({
        store: { async save() {} },
        timeoutMs: 80,
        openURL: async (url) => {
          const parsed = new URL(url);
          const response = await fetch(
            `http://127.0.0.1:${parsed.searchParams.get("callback_port")}/callback`,
            {
              method: "POST",
              headers: { "content-type": "application/x-www-form-urlencoded" },
              body: new URLSearchParams({
                ticket: "wrong-state-ticket",
                refresh_token: "wrong-state-refresh",
                state: "b".repeat(43),
              }),
            },
          );
          callbackStatus = response.status;
        },
      }),
    /timed out/i,
  );
  assert.equal(callbackStatus, 400);
});

test("ticket refresh uses the domestic endpoint and never returns refresh credentials", async () => {
  let captured;
  const ticket = jwtWithExpiry(Math.floor(Date.now() / 1000) + 3600);
  const result = await refreshTicket("refresh-value", {
    fetchImpl: async (url, options) => {
      captured = { url, options };
      return new Response(JSON.stringify({ code: 0, result: { token: ticket } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });
  assert.equal(captured.url, "https://goudaai.com/prod-api/user/apikey2token");
  assert.equal(captured.options.method, "GET");
  assert.equal(captured.options.headers["Refresh-Token"], "refresh-value");
  assert.equal(result, ticket);
  assert.equal(ticketNeedsRefresh(ticket, Date.now()), false);
  assert.equal(
    ticketNeedsRefresh(jwtWithExpiry(Math.floor(Date.now() / 1000) + 30), Date.now()),
    true,
  );
});

test("an invalid refresh clears credentials and requires a new login", async () => {
  let deleted = false;
  const store = {
    backend: "file",
    async load() {
      return {
        ticket: jwtWithExpiry(Math.floor(Date.now() / 1000) + 10),
        refresh_token: "invalid-refresh",
      };
    },
    async save() {
      throw new Error("must not save rejected credentials");
    },
    async delete() {
      deleted = true;
    },
  };
  const provider = new AuthProvider(store, {
    fetchImpl: async () =>
      new Response(JSON.stringify({ code: 1007, message: "invalid" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  });
  await assert.rejects(() => provider.accessToken(), (error) => error.code === "LOGIN_REQUIRED");
  assert.equal(deleted, true);
});
