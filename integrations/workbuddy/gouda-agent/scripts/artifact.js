"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const { PROFILE } = require("./config");

const IMAGE_EXTENSIONS = /\.(?:jpe?g|png|webp)$/i;
const DEFAULT_LIMITS = Object.freeze({
  image: 100 * 1024 * 1024,
  audio: 500 * 1024 * 1024,
  video: 5 * 1024 * 1024 * 1024,
});

function invalid(message) {
  const error = new Error(message);
  error.code = "INVALID_ARGUMENT";
  return error;
}

function expectedHost(mediaType) {
  return new URL(mediaType === "image" ? PROFILE.imagePrefix : PROFILE.mediaPrefix)
    .hostname;
}

function validateExistingURL(mediaType, value) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw invalid("artifact URL is invalid");
  }
  if (
    parsed.protocol !== "https:" ||
    parsed.username ||
    parsed.password ||
    (parsed.port && parsed.port !== "443") ||
    parsed.hostname.toLowerCase() !== expectedHost(mediaType).toLowerCase()
  ) {
    throw invalid("artifact URL host is not allowed for media type");
  }
  return parsed.toString();
}

function escapeOSSKey(value) {
  if (
    value.startsWith("/") ||
    /[\\?#]/.test(value) ||
    /[\u0000-\u001f\u007f]/.test(value)
  ) {
    throw invalid("artifact OSS key contains unsafe path data");
  }
  const segments = value.split("/");
  if (segments.some((segment) => !segment || segment === "." || segment === "..")) {
    throw invalid("artifact OSS key contains an unsafe path segment");
  }
  return segments.map(encodeURIComponent).join("/");
}

function resolveArtifactURL(mediaType, rawKey) {
  const normalizedType = String(mediaType || "").trim().toLowerCase();
  if (!["image", "video", "audio", "document"].includes(normalizedType)) {
    throw invalid("media type must be image, video, audio, or document");
  }
  let key = String(rawKey || "").trim();
  if (!key) {
    throw invalid("artifact OSS key is required");
  }
  if (key.includes("://")) {
    return validateExistingURL(normalizedType, key);
  }
  if (normalizedType === "image" && !IMAGE_EXTENSIONS.test(key)) {
    key += ".jpg";
  }
  if (normalizedType === "video" && !/\.mp4$/i.test(key)) {
    key += ".mp4";
  }
  const prefix = normalizedType === "image" ? PROFILE.imagePrefix : PROFILE.mediaPrefix;
  return prefix + escapeOSSKey(key);
}

function matchesMediaType(mediaType, contentType) {
  return contentType.toLowerCase().startsWith(`${mediaType}/`);
}

function previewExtension(mediaType, resolvedURL) {
  const allowed = {
    image: new Set([".jpg", ".jpeg", ".png", ".webp"]),
    video: new Set([".mp4", ".mov", ".webm"]),
    audio: new Set([".mp3", ".m4a", ".wav", ".aac", ".ogg"]),
  };
  const fallback = { image: ".jpg", video: ".mp4", audio: ".mp3" };
  const extension = path.extname(new URL(resolvedURL).pathname).toLowerCase();
  return allowed[mediaType]?.has(extension) ? extension : fallback[mediaType];
}

class ArtifactDownloader {
  constructor({ fetchImpl = globalThis.fetch, limits = DEFAULT_LIMITS } = {}) {
    if (typeof fetchImpl !== "function") {
      throw new Error("fetch implementation is required");
    }
    this.fetchImpl = fetchImpl;
    this.limits = { ...DEFAULT_LIMITS, ...limits };
  }

  async download(mediaType, contentID, outputPath) {
    const normalizedType = String(mediaType || "").trim().toLowerCase();
    const limit = this.limits[normalizedType];
    if (!Number.isSafeInteger(limit) || limit <= 0) {
      throw invalid("artifact media type cannot be downloaded");
    }
    const resolvedURL = resolveArtifactURL(normalizedType, contentID);
    if (typeof outputPath !== "string" || !path.isAbsolute(outputPath)) {
      throw invalid("artifact output path must be absolute");
    }
    const destination = path.normalize(outputPath);
    try {
      await fs.lstat(destination);
      throw invalid("artifact output path already exists");
    } catch (error) {
      if (error && error.code !== "ENOENT") {
        throw error;
      }
    }
    let parent;
    try {
      parent = await fs.stat(path.dirname(destination));
    } catch {
      throw invalid("artifact output directory is unavailable");
    }
    if (!parent.isDirectory()) {
      throw invalid("artifact output directory is unavailable");
    }

    let response;
    try {
      response = await this.fetchImpl(resolvedURL, {
        method: "GET",
        redirect: "error",
        signal: AbortSignal.timeout(30 * 60 * 1000),
      });
    } catch {
      throw new Error("artifact download failed");
    }
    if (!response.ok) {
      throw new Error(`artifact download failed with HTTP ${response.status}`);
    }
    const contentType = String(response.headers.get("content-type") || "")
      .split(";", 1)[0]
      .trim()
      .toLowerCase();
    if (!matchesMediaType(normalizedType, contentType)) {
      throw new Error("artifact content type does not match media type");
    }
    const contentLength = Number(response.headers.get("content-length"));
    if (Number.isFinite(contentLength) && contentLength > limit) {
      throw new Error("artifact exceeds download size limit");
    }
    if (!response.body) {
      throw new Error("artifact response body is unavailable");
    }

    const temporary = path.join(
      path.dirname(destination),
      `.${path.basename(destination)}.gouda-${crypto.randomUUID()}.tmp`,
    );
    let handle;
    let bytes = 0;
    try {
      handle = await fs.open(temporary, "wx", 0o600);
      for await (const rawChunk of response.body) {
        const chunk = Buffer.from(rawChunk);
        bytes += chunk.length;
        if (bytes > limit) {
          throw new Error("artifact exceeds download size limit");
        }
        await handle.write(chunk);
      }
      await handle.sync();
      await handle.close();
      handle = null;
      try {
        await fs.link(temporary, destination);
      } catch (error) {
        if (error && error.code === "EEXIST") {
          throw invalid("artifact output path already exists");
        }
        throw new Error("artifact could not be published");
      }
    } finally {
      if (handle) {
        await handle.close().catch(() => {});
      }
      await fs.unlink(temporary).catch(() => {});
    }
    return { path: destination, bytes, content_type: contentType };
  }

  async preview(mediaType, contentID) {
    const normalizedType = String(mediaType || "").trim().toLowerCase();
    const resolvedURL = resolveArtifactURL(normalizedType, contentID);
    if (!DEFAULT_LIMITS[normalizedType]) {
      throw invalid("artifact media type cannot be previewed");
    }
    const directory = await fs.mkdtemp(path.join(os.tmpdir(), "gouda-agent-preview-"));
    try {
      return await this.download(
        normalizedType,
        resolvedURL,
        path.join(directory, `preview${previewExtension(normalizedType, resolvedURL)}`),
      );
    } catch (error) {
      await fs.rm(directory, { recursive: true, force: true });
      throw error;
    }
  }
}

module.exports = {
  ArtifactDownloader,
  DEFAULT_LIMITS,
  escapeOSSKey,
  matchesMediaType,
  previewExtension,
  resolveArtifactURL,
};
