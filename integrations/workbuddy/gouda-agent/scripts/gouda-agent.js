#!/usr/bin/env node
"use strict";

const { ArtifactDownloader, resolveArtifactURL } = require("./artifact");
const { AuthProvider, login } = require("./auth");
const { GoudaClient } = require("./client");
const { PROFILE } = require("./config");
const { CredentialStore, defaultDataDirectory } = require("./credentials");
const { uploadAttachment, validateAttachments } = require("./oss");
const { writeFailure, writeRecord, writeSuccess } = require("./output");
const { decodeSSE, terminalType } = require("./sse");
const { StateStore } = require("./state");

const EXIT_USAGE = 10;
const EXIT_AUTH = 20;
const EXIT_BUSINESS = 30;
const EXIT_DEPENDENCY = 40;
const EXIT_NETWORK = 50;

function parseFlags(args) {
  const flags = {};
  for (let index = 0; index < args.length; index += 1) {
    const name = args[index];
    if (!name.startsWith("--")) {
      throw Object.assign(new Error(`unexpected argument: ${name}`), {
        code: "INVALID_ARGUMENT",
      });
    }
    const key = name.slice(2);
    if (key === "image-search") {
      flags[key] = true;
      continue;
    }
    const value = args[index + 1];
    if (value === undefined || value.startsWith("--")) {
      throw Object.assign(new Error(`missing value for --${key}`), {
        code: "INVALID_ARGUMENT",
      });
    }
    index += 1;
    if (key === "file") {
      flags.file = [...(flags.file || []), value];
    } else {
      flags[key] = value;
    }
  }
  return flags;
}

function positiveInteger(raw, fallback, name, { allowZero = false } = {}) {
  if (raw === undefined) {
    return fallback;
  }
  const value = Number(raw);
  if (!Number.isInteger(value) || value < (allowZero ? 0 : 1)) {
    throw Object.assign(new Error(`${name} is invalid`), { code: "INVALID_ARGUMENT" });
  }
  return value;
}

function requireFlag(flags, name) {
  const value = String(flags[name] || "").trim();
  if (!value) {
    throw Object.assign(new Error(`--${name} is required`), {
      code: "INVALID_ARGUMENT",
    });
  }
  return value;
}

function projectDeepLink(projectID, conversationID) {
  if (!projectID || !conversationID) {
    throw Object.assign(
      new Error("project and conversation identifiers are required"),
      { code: "INVALID_ARGUMENT" },
    );
  }
  const url = new URL("/new-chat", PROFILE.webBaseURL);
  url.searchParams.set("project_id", projectID);
  url.searchParams.set("conversation_id", conversationID);
  return url.toString();
}

function exitCodeFor(error) {
  if (error && (error.code === "INVALID_ARGUMENT" || error.code === "STATE_NOT_FOUND")) {
    return EXIT_USAGE;
  }
  if (error && error.code === "LOGIN_REQUIRED") {
    return EXIT_AUTH;
  }
  if (
    error &&
    error.code === "HTTP_ERROR" &&
    (error.statusCode === 401 || error.statusCode === 403)
  ) {
    return EXIT_AUTH;
  }
  if (
    error &&
    (error.code === "BUSINESS_ERROR" ||
      error.code === "PROJECT_CONVERSATION_CONFLICT" ||
      error.code === "HTTP_ERROR")
  ) {
    return EXIT_BUSINESS;
  }
  if (error && error.code === "DEPENDENCY_ERROR") {
    return EXIT_DEPENDENCY;
  }
  if (error && error.code === "NETWORK_ERROR") {
    return EXIT_NETWORK;
  }
  return 1;
}

async function emitStream(stream, context) {
  const { stdout, stateStore, projectID = "", previous = {} } = context;
  if (!stream.turnID) {
    throw Object.assign(new Error("stream response is missing turn ID"), {
      code: "PROTOCOL_ERROR",
    });
  }
  const baseState = {
    ...(previous.project_id ? { project_id: previous.project_id } : {}),
    ...(projectID ? { project_id: projectID } : {}),
    ...(stream.conversationID || previous.conversation_id
      ? { conversation_id: stream.conversationID || previous.conversation_id }
      : {}),
    turn_id: stream.turnID,
  };
  await stateStore.upsert({ ...baseState, status: "running" });
  writeRecord(stdout, {
    type: "session",
    conversation_id: baseState.conversation_id || "",
    turn_id: stream.turnID,
  });

  let lastEventID = previous.last_event_id || "";
  let terminal = "";
  try {
    for await (const event of decodeSSE(stream.body)) {
      writeRecord(stdout, { type: "event", ...event });
      if (event.event_id) {
        lastEventID = event.event_id;
      }
      terminal = terminalType(event) || terminal;
      await stateStore.upsert({
        ...baseState,
        ...(lastEventID ? { last_event_id: lastEventID } : {}),
        status:
          terminal === "RUN_FINISHED"
            ? "finished"
            : terminal === "RUN_ERROR"
              ? "failed"
              : "running",
      });
    }
  } catch {
    terminal = "";
  }
  if (terminal === "RUN_FINISHED") {
    return 0;
  }
  if (terminal === "RUN_ERROR") {
    return EXIT_BUSINESS;
  }
  await stateStore.upsert({
    ...baseState,
    ...(lastEventID ? { last_event_id: lastEventID } : {}),
    status: "interrupted",
  });
  writeRecord(stdout, {
    type: "stream_error",
    conversation_id: baseState.conversation_id || "",
    turn_id: stream.turnID,
    last_event_id: lastEventID || null,
    error: {
      code: "STREAM_ENDED_EARLY",
      message:
        "SSE stream ended before RUN_FINISHED or RUN_ERROR; resume the turn with last_event_id",
    },
  });
  return EXIT_NETWORK;
}

async function run(rawArgs, dependencies = {}) {
  const stdout = dependencies.stdout || process.stdout;
  const stderr = dependencies.stderr || process.stderr;
  const args = [...rawArgs];
  if (args[0] === "--json" || args[0] === "--jsonl") {
    args.shift();
  }

  try {
    const [command, subcommand, ...rest] = args;
    if (command === "doctor" && subcommand === undefined) {
      const major = Number(process.versions.node.split(".")[0]);
      writeSuccess(stdout, {
        ok: major >= 18,
        node_version: process.versions.node,
        profile: PROFILE.name,
        api_origin: PROFILE.apiBaseURL,
        login_url: PROFILE.loginURL,
        data_directory: defaultDataDirectory(),
      });
      return major >= 18 ? 0 : EXIT_DEPENDENCY;
    }

    const credentialStore = dependencies.credentialStore || new CredentialStore();
    const authProvider =
      dependencies.authProvider || new AuthProvider(credentialStore, dependencies.authOptions);
    const client =
      dependencies.client ||
      new GoudaClient({ tokenProvider: () => authProvider.accessToken() });
    const stateStore = dependencies.stateStore || new StateStore();
    const loginImpl = dependencies.loginImpl || login;
    const validateAttachmentsImpl =
      dependencies.validateAttachmentsImpl || validateAttachments;
    const uploadAttachmentImpl = dependencies.uploadAttachmentImpl || uploadAttachment;

    if (command === "auth") {
      const flags = parseFlags(rest);
      if (Object.keys(flags).length) {
        throw Object.assign(new Error("auth command does not accept flags"), {
          code: "INVALID_ARGUMENT",
        });
      }
      if (subcommand === "status") {
        writeSuccess(stdout, await authProvider.status());
        return 0;
      }
      if (subcommand === "login") {
        const result = await loginImpl({
          store: credentialStore,
          onManualURL: (url) => stderr.write(`Open this login URL in a browser: ${url}\n`),
        });
        writeSuccess(stdout, result);
        return 0;
      }
      if (subcommand === "refresh") {
        await authProvider.forceRefresh();
        writeSuccess(stdout, { refreshed: true, backend: credentialStore.backend });
        return 0;
      }
      if (subcommand === "logout") {
        await credentialStore.delete();
        writeSuccess(stdout, { logged_out: true });
        return 0;
      }
    }

    if (command === "project") {
      const flags = parseFlags(rest);
      if (subcommand === "create") {
        writeSuccess(stdout, await client.createProject(requireFlag(flags, "name")));
        return 0;
      }
      if (subcommand === "list") {
        writeSuccess(
          stdout,
          await client.listProjects(
            positiveInteger(flags["page-no"], 0, "page number", { allowZero: true }),
            positiveInteger(flags["page-size"], 20, "page size"),
          ),
        );
        return 0;
      }
      if (subcommand === "detail") {
        writeSuccess(stdout, await client.projectDetail(requireFlag(flags, "project-id")));
        return 0;
      }
      if (subcommand === "assets") {
        const pageSize = positiveInteger(flags["page-size"], 20, "page size");
        if (pageSize > 100) {
          throw Object.assign(new Error("page size is invalid"), {
            code: "INVALID_ARGUMENT",
          });
        }
        const offset = flags.offset === undefined
          ? null
          : positiveInteger(flags.offset, 0, "offset", { allowZero: true });
        writeSuccess(stdout, await client.listProjectAssets(offset, pageSize));
        return 0;
      }
      if (subcommand === "link") {
        const projectID = requireFlag(flags, "project-id");
        const conversationID = requireFlag(flags, "conversation-id");
        writeSuccess(stdout, {
          project_id: projectID,
          conversation_id: conversationID,
          deep_link: projectDeepLink(projectID, conversationID),
          profile: PROFILE.name,
        });
        return 0;
      }
    }

    if (command === "artifact") {
      const flags = parseFlags(rest);
      const mediaType = requireFlag(flags, "media-type");
      if (flags["content-id"] && flags["oss-key"]) {
        throw Object.assign(new Error("use only one artifact identifier flag"), {
          code: "INVALID_ARGUMENT",
        });
      }
      const contentID = String(flags["content-id"] || flags["oss-key"] || "").trim();
      if (!contentID) {
        throw Object.assign(new Error("--content-id is required"), {
          code: "INVALID_ARGUMENT",
        });
      }
      if (subcommand === "url") {
        writeSuccess(stdout, { url: resolveArtifactURL(mediaType, contentID) });
        return 0;
      }
      if (subcommand === "preview") {
        const downloader = dependencies.artifactDownloader || new ArtifactDownloader();
        writeSuccess(stdout, await downloader.preview(mediaType, contentID));
        return 0;
      }
      if (subcommand === "download") {
        const downloader = dependencies.artifactDownloader || new ArtifactDownloader();
        writeSuccess(
          stdout,
          await downloader.download(
            mediaType,
            contentID,
            requireFlag(flags, "output"),
          ),
        );
        return 0;
      }
    }

    if (command === "state") {
      const flags = parseFlags(rest);
      if (subcommand === "list") {
        writeSuccess(stdout, { tasks: await stateStore.list() });
        return 0;
      }
      if (subcommand === "show") {
        writeSuccess(stdout, await stateStore.show(requireFlag(flags, "turn-id")));
        return 0;
      }
    }

    if (command === "cancel") {
      const flags = parseFlags(args.slice(1));
      writeSuccess(
        stdout,
        await client.cancel(
          requireFlag(flags, "conversation-id"),
          requireFlag(flags, "turn-id"),
        ),
      );
      return 0;
    }

    if (command === "history") {
      const flags = parseFlags(args.slice(1));
      writeSuccess(
        stdout,
        await client.history(
          requireFlag(flags, "conversation-id"),
          positiveInteger(flags["page-no"], 0, "page number", { allowZero: true }),
          positiveInteger(flags["page-size"], 20, "page size"),
        ),
      );
      return 0;
    }

    if (command === "ask") {
      const flags = parseFlags(args.slice(1));
      const prompt = requireFlag(flags, "prompt");
      const projectID = String(flags["project-id"] || "").trim();
      const conversationID = String(flags["conversation-id"] || "").trim();
      if (Boolean(projectID) === Boolean(conversationID)) {
        throw Object.assign(
          new Error("exactly one of --project-id or --conversation-id is required"),
          { code: "INVALID_ARGUMENT" },
        );
      }
      const files = flags.file || [];
      const uploaded = [];
      for (const attachment of await validateAttachmentsImpl(files)) {
        uploaded.push(
          await uploadAttachmentImpl(attachment, {
            getCredentials: (bucket) => client.getOSSCredentials(bucket),
          }),
        );
      }
      const stream = await client.ask(prompt, {
        projectID,
        conversationID,
        imageSearchEnabled: Boolean(flags["image-search"]),
        attachments: uploaded,
      });
      return emitStream(stream, { stdout, stateStore, projectID });
    }

    if (command === "resume") {
      const flags = parseFlags(args.slice(1));
      const turnID = requireFlag(flags, "turn-id");
      let previous = {};
      try {
        previous = await stateStore.show(turnID);
      } catch (error) {
        if (!error || error.code !== "STATE_NOT_FOUND") {
          throw error;
        }
      }
      const stream = await client.resume(turnID, String(flags["last-event-id"] || ""));
      return emitStream(stream, { stdout, stateStore, previous });
    }

    throw Object.assign(new Error("unsupported command"), { code: "INVALID_ARGUMENT" });
  } catch (error) {
    writeFailure(stdout, error);
    return exitCodeFor(error);
  }
}

if (require.main === module) {
  run(process.argv.slice(2)).then((exitCode) => {
    process.exitCode = exitCode;
  });
}

module.exports = {
  emitStream,
  parseFlags,
  projectDeepLink,
  run,
};
