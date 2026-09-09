"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const {
  CredentialStore,
  defaultDataDirectory,
} = require("../../gouda-agent/scripts/credentials");
const { StateStore } = require("../../gouda-agent/scripts/state");

test("credential store is private, atomic, and isolated from the Go CLI", async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gouda-credentials-test-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const credentialPath = path.join(root, "workbuddy", "gouda-agent", "credentials.json");
  const store = new CredentialStore(credentialPath);

  await store.save({ ticket: "private-ticket", refresh_token: "private-refresh" });
  assert.deepEqual(await store.load(), {
    ticket: "private-ticket",
    refresh_token: "private-refresh",
  });
  if (process.platform !== "win32") {
    assert.equal((await fs.stat(path.dirname(credentialPath))).mode & 0o777, 0o700);
    assert.equal((await fs.stat(credentialPath)).mode & 0o777, 0o600);
  }
  assert.equal(defaultDataDirectory().includes("vivago-agent-cli"), false);

  await store.delete();
  await assert.rejects(() => store.load(), (error) => error.code === "LOGIN_REQUIRED");
});

test("credential store rejects a symlink target", async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gouda-symlink-test-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const target = path.join(root, "target.json");
  const link = path.join(root, "credentials.json");
  await fs.writeFile(target, "{}", { mode: 0o600 });
  await fs.symlink(target, link);
  const store = new CredentialStore(link);
  await assert.rejects(
    () => store.save({ ticket: "private-ticket", refresh_token: "private-refresh" }),
    /symbolic link/i,
  );
});

test("state store persists identifiers and cursors but rejects transcript fields", async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gouda-state-test-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const store = new StateStore(path.join(root, "state.json"));

  await store.upsert({
    project_id: "project-1",
    conversation_id: "conversation-1",
    turn_id: "turn-1",
    last_event_id: "event-1",
    status: "running",
  });
  const entry = await store.show("turn-1");
  assert.equal(entry.project_id, "project-1");
  assert.equal(entry.conversation_id, "conversation-1");
  assert.equal(entry.turn_id, "turn-1");
  assert.equal(entry.last_event_id, "event-1");
  assert.equal(entry.status, "running");
  assert.match(entry.updated_at, /^\d{4}-\d{2}-\d{2}T/);
  await assert.rejects(
    () =>
      store.upsert({
        turn_id: "turn-2",
        status: "running",
        prompt: "must not be stored",
      }),
    /not allowed/i,
  );
});
