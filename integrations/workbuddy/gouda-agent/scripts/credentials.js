"use strict";

const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");

function defaultDataDirectory() {
  return path.join(os.homedir(), ".workbuddy-skills", "gouda-agent");
}

function loginRequired() {
  const error = new Error("Gouda Agent login is required");
  error.code = "LOGIN_REQUIRED";
  return error;
}

async function lstatOrNull(target) {
  try {
    return await fs.lstat(target);
  } catch (error) {
    if (error && error.code === "ENOENT") {
      return null;
    }
    throw error;
  }
}

async function ensurePrivateDirectory(directory) {
  const existing = await lstatOrNull(directory);
  if (existing && existing.isSymbolicLink()) {
    throw new Error("private data directory must not be a symbolic link");
  }
  if (existing && !existing.isDirectory()) {
    throw new Error("private data directory must be a directory");
  }
  if (!existing) {
    await fs.mkdir(directory, { recursive: true, mode: 0o700 });
  }
  if (process.platform !== "win32") {
    await fs.chmod(directory, 0o700);
  }
}

async function rejectSymlinkTarget(target) {
  const existing = await lstatOrNull(target);
  if (existing && existing.isSymbolicLink()) {
    throw new Error("private data file must not be a symbolic link");
  }
  if (existing && !existing.isFile()) {
    throw new Error("private data file must be a regular file");
  }
  return existing;
}

async function atomicWriteJSON(target, value) {
  const directory = path.dirname(target);
  await ensurePrivateDirectory(directory);
  await rejectSymlinkTarget(target);
  const temporary = path.join(
    directory,
    `.tmp-${process.pid}-${crypto.randomBytes(8).toString("hex")}`,
  );
  try {
    await fs.writeFile(temporary, JSON.stringify(value), {
      encoding: "utf8",
      mode: 0o600,
      flag: "wx",
    });
    if (process.platform !== "win32") {
      await fs.chmod(temporary, 0o600);
    }
    await fs.rename(temporary, target);
  } finally {
    await fs.rm(temporary, { force: true }).catch(() => {});
  }
}

async function readPrivateJSON(target, missingError) {
  const existing = await rejectSymlinkTarget(target);
  if (!existing) {
    throw missingError;
  }
  if (process.platform !== "win32" && (existing.mode & 0o777) !== 0o600) {
    throw new Error("private data file permissions must be 0600");
  }
  let parsed;
  try {
    parsed = JSON.parse(await fs.readFile(target, "utf8"));
  } catch (error) {
    if (error && error.code === "ENOENT") {
      throw missingError;
    }
    throw new Error("private data file is invalid");
  }
  return parsed;
}

class CredentialStore {
  constructor(credentialPath = path.join(defaultDataDirectory(), "credentials.json")) {
    this.path = credentialPath;
    this.backend = "file";
  }

  async save(credentials) {
    if (
      !credentials ||
      typeof credentials.ticket !== "string" ||
      !credentials.ticket.trim() ||
      typeof credentials.refresh_token !== "string" ||
      !credentials.refresh_token.trim()
    ) {
      throw new Error("ticket and refresh token are required");
    }
    await atomicWriteJSON(this.path, {
      ticket: credentials.ticket.trim(),
      refresh_token: credentials.refresh_token.trim(),
    });
  }

  async load() {
    const credentials = await readPrivateJSON(this.path, loginRequired());
    if (
      typeof credentials.ticket !== "string" ||
      !credentials.ticket ||
      typeof credentials.refresh_token !== "string" ||
      !credentials.refresh_token
    ) {
      throw new Error("credential file is incomplete");
    }
    return credentials;
  }

  async delete() {
    await rejectSymlinkTarget(this.path);
    await fs.rm(this.path, { force: true });
  }
}

module.exports = {
  CredentialStore,
  atomicWriteJSON,
  readPrivateJSON,
  defaultDataDirectory,
  loginRequired,
};
