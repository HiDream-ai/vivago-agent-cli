"use strict";

const path = require("node:path");

const {
  atomicWriteJSON,
  readPrivateJSON,
  defaultDataDirectory,
} = require("./credentials");

const ALLOWED_FIELDS = new Set([
  "project_id",
  "conversation_id",
  "turn_id",
  "last_event_id",
  "status",
  "created_at",
  "updated_at",
]);

class StateStore {
  constructor(statePath = path.join(defaultDataDirectory(), "state.json")) {
    this.path = statePath;
  }

  async read() {
    const missing = new Error("state file not found");
    missing.code = "STATE_NOT_FOUND";
    try {
      const value = await readPrivateJSON(this.path, missing);
      return Array.isArray(value.tasks) ? value : { tasks: [] };
    } catch (error) {
      if (error && error.code === "STATE_NOT_FOUND") {
        return { tasks: [] };
      }
      throw error;
    }
  }

  async upsert(entry) {
    for (const key of Object.keys(entry || {})) {
      if (!ALLOWED_FIELDS.has(key)) {
        throw new Error(`state field ${key} is not allowed`);
      }
    }
    if (!entry || !String(entry.turn_id || "").trim()) {
      throw new Error("turn_id is required");
    }
    const document = await this.read();
    const now = new Date().toISOString();
    const index = document.tasks.findIndex((item) => item.turn_id === entry.turn_id);
    const previous = index >= 0 ? document.tasks[index] : {};
    const next = {
      ...previous,
      ...entry,
      turn_id: String(entry.turn_id).trim(),
      created_at: previous.created_at || entry.created_at || now,
      updated_at: now,
    };
    if (index >= 0) {
      document.tasks[index] = next;
    } else {
      document.tasks.push(next);
    }
    await atomicWriteJSON(this.path, document);
    return next;
  }

  async list() {
    const document = await this.read();
    return [...document.tasks].sort((left, right) =>
      String(right.updated_at || "").localeCompare(String(left.updated_at || "")),
    );
  }

  async show(turnID) {
    const document = await this.read();
    const found = document.tasks.find((item) => item.turn_id === turnID);
    if (!found) {
      const error = new Error("turn state was not found");
      error.code = "STATE_NOT_FOUND";
      throw error;
    }
    return found;
  }
}

module.exports = { StateStore, ALLOWED_FIELDS };
