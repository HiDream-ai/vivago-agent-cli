"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const fsPromises = require("node:fs/promises");
const https = require("node:https");
const path = require("node:path");

const { PROFILE } = require("./config");
const { escapeOSSKey } = require("./artifact");

// This is the public Web-client compatibility cipher configuration shipped in the deployed
// goudaai.com JavaScript bundle. It is not an OSS credential. The actual STS values are short-lived,
// user-scoped, held only in memory, and never included in command output.
const PUBLIC_CLIENT_CIPHER_CONFIG = Object.freeze({
  key: "uf6ad3975mda52p41i4ssxndyw2ph0li",
  iv: "vmrknm2659ai9826",
});

const FORMATS = Object.freeze({
  ".jpg": ["image", "image", "image/jpeg"],
  ".jpeg": ["image", "image", "image/jpeg"],
  ".png": ["image", "image", "image/png"],
  ".mp4": ["video", "media", "video/mp4"],
  ".mp3": ["audio", "media", "audio/mpeg"],
  ".doc": ["document", "media", "application/msword"],
  ".docx": [
    "document",
    "media",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ],
  ".txt": ["document", "media", "text/plain"],
  ".md": ["document", "media", "text/markdown"],
  ".pdf": ["document", "media", "application/pdf"],
  ".srt": ["document", "media", "application/x-subrip"],
  ".vtt": ["document", "media", "text/vtt"],
  ".ass": ["document", "media", "text/x-ssa"],
  ".ssa": ["document", "media", "text/x-ssa"],
});

const COUNT_LIMITS = Object.freeze({ image: 9, video: 1, audio: 1, document: 4 });
const SIZE_LIMITS = Object.freeze({
  image: 50 * 1024 * 1024,
  video: 300 * 1024 * 1024,
  audio: 15 * 1024 * 1024,
  document: 1024 * 1024,
});

function objectKeyFor(mediaType, extension) {
  const identifier = crypto.randomUUID();
  if (mediaType === "image") {
    return `${extension === ".jpg" || extension === ".jpeg" ? "j" : "p"}_${identifier}`;
  }
  return identifier + extension;
}

async function validateAttachments(paths) {
  const results = [];
  const counts = { image: 0, video: 0, audio: 0, document: 0 };
  const documentExtensions = new Set();
  for (const rawPath of paths || []) {
    if (typeof rawPath !== "string" || !rawPath.trim()) {
      throw new Error("attachment path is required");
    }
    const absolutePath = path.resolve(rawPath);
    let stat;
    try {
      stat = await fsPromises.lstat(absolutePath);
    } catch {
      throw new Error("attachment must be a readable regular file");
    }
    if (!stat.isFile() || stat.isSymbolicLink()) {
      throw new Error("attachment must be a regular file and not a symbolic link");
    }
    const extension = path.extname(absolutePath).toLowerCase();
    const format = FORMATS[extension];
    if (!format) {
      throw new Error("attachment format is not supported");
    }
    const [mediaType, bucket, contentType] = format;
    counts[mediaType] += 1;
    if (counts[mediaType] > COUNT_LIMITS[mediaType]) {
      throw new Error("too many attachments for media type");
    }
    if (stat.size > SIZE_LIMITS[mediaType]) {
      throw new Error("attachment exceeds the size limit");
    }
    if (mediaType === "document") {
      if (documentExtensions.has(extension)) {
        throw new Error("only one document of each format is allowed");
      }
      documentExtensions.add(extension);
    }
    const handle = await fsPromises.open(absolutePath, "r");
    await handle.close();
    results.push({
      path: absolutePath,
      name: path.basename(absolutePath),
      extension,
      mediaType,
      bucket,
      contentType,
      size: stat.size,
      objectKey: objectKeyFor(mediaType, extension),
    });
  }
  return results;
}

function decryptCredentialEnvelope(ciphertext) {
  try {
    const decipher = crypto.createDecipheriv(
      "aes-256-cbc",
      Buffer.from(PUBLIC_CLIENT_CIPHER_CONFIG.key, "utf8"),
      Buffer.from(PUBLIC_CLIENT_CIPHER_CONFIG.iv, "utf8"),
    );
    const plaintext = Buffer.concat([
      decipher.update(Buffer.from(ciphertext, "base64")),
      decipher.final(),
    ]).toString("utf8");
    return JSON.parse(plaintext);
  } catch {
    throw new Error("domestic OSS credential response could not be decoded");
  }
}

function validateCredentialFields(value) {
  const fields = ["AccessKeyId", "AccessKeySecret", "SecurityToken", "BucketName"];
  if (!value || typeof value !== "object") {
    throw new Error("domestic OSS credential response is invalid");
  }
  for (const field of fields) {
    if (
      typeof value[field] !== "string" ||
      !value[field].trim() ||
      /[\r\n]/.test(value[field])
    ) {
      throw new Error(`domestic OSS credential response is missing ${field}`);
    }
  }
  const bucket = value.BucketName.trim();
  if (!/^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/.test(bucket)) {
    throw new Error("domestic OSS bucket name is invalid");
  }
  return Object.fromEntries(fields.map((field) => [field, value[field].trim()]));
}

function extractOSSCredentials(response) {
  const result = response && response.result;
  const candidate =
    result && result.AccessKeySecret && result.SecurityToken
      ? result
      : result && typeof result.data === "string"
        ? decryptCredentialEnvelope(result.data)
        : null;
  return validateCredentialFields(candidate);
}

function buildAliyunPutRequest(credentials, attachment, date = new Date().toUTCString()) {
  const validated = validateCredentialFields(credentials);
  const objectKey = String(attachment.objectKey || "").trim();
  const contentType = String(attachment.contentType || "").trim();
  if (!objectKey || !contentType || !Number.isSafeInteger(attachment.size) || attachment.size < 0) {
    throw new Error("attachment upload metadata is invalid");
  }
  const canonicalHeaders = `x-oss-security-token:${validated.SecurityToken}\n`;
  const canonicalResource = `/${validated.BucketName}/${objectKey}`;
  const stringToSign = [
    "PUT",
    "",
    contentType,
    date,
    canonicalHeaders + canonicalResource,
  ].join("\n");
  const signature = crypto
    .createHmac("sha1", validated.AccessKeySecret)
    .update(stringToSign)
    .digest("base64");
  return {
    hostname: `${validated.BucketName}.${PROFILE.aliyunRegion}.aliyuncs.com`,
    port: 443,
    path: "/" + escapeOSSKey(objectKey),
    method: "PUT",
    headers: {
      "Content-Type": contentType,
      "Content-Length": attachment.size,
      Date: date,
      "x-oss-security-token": validated.SecurityToken,
      Authorization: `OSS ${validated.AccessKeyId}:${signature}`,
    },
  };
}

async function putObject(attachment, credentials, { requestImpl = https.request } = {}) {
  const requestOptions = buildAliyunPutRequest(credentials, attachment);
  await new Promise((resolve, reject) => {
    const request = requestImpl(requestOptions, (response) => {
      response.resume();
      if (response.statusCode >= 200 && response.statusCode < 300) {
        response.once("end", resolve);
      } else {
        response.once("end", () =>
          reject(new Error(`domestic OSS upload failed with HTTP ${response.statusCode}`)),
        );
      }
    });
    request.once("error", () => reject(new Error("domestic OSS upload failed")));
    const input = fs.createReadStream(attachment.path);
    input.once("error", () => {
      request.destroy();
      reject(new Error("attachment could not be read"));
    });
    input.pipe(request);
  });
}

async function uploadAttachment(attachment, { getCredentials, putObject: put = putObject }) {
  const response = await getCredentials(attachment.bucket);
  const credentials = extractOSSCredentials(response);
  await put(attachment, credentials);
  return {
    name: attachment.name,
    mediaType: attachment.mediaType,
    ossKey: attachment.objectKey,
  };
}

module.exports = {
  PUBLIC_CLIENT_CIPHER_CONFIG,
  buildAliyunPutRequest,
  decryptCredentialEnvelope,
  extractOSSCredentials,
  objectKeyFor,
  putObject,
  uploadAttachment,
  validateAttachments,
};
