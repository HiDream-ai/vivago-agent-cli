"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const {
  PUBLIC_CLIENT_CIPHER_CONFIG,
  buildAliyunPutRequest,
  extractOSSCredentials,
  validateAttachments,
  uploadAttachment,
} = require("../../gouda-agent/scripts/oss");

const TEST_CREDENTIALS = {
  AccessKeyId: "access-value",
  AccessKeySecret: "secret-value",
  SecurityToken: "session-value",
  BucketName: "demo-bucket",
};

test("attachment validation uses domestic image/media categories", async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gouda-attachment-test-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const image = path.join(root, "reference.png");
  const document = path.join(root, "notes.md");
  await fs.writeFile(image, "image");
  await fs.writeFile(document, "notes");

  const attachments = await validateAttachments([image, document]);
  assert.deepEqual(
    attachments.map((item) => ({
      name: item.name,
      mediaType: item.mediaType,
      bucket: item.bucket,
      contentType: item.contentType,
    })),
    [
      {
        name: "reference.png",
        mediaType: "image",
        bucket: "image",
        contentType: "image/png",
      },
      {
        name: "notes.md",
        mediaType: "document",
        bucket: "media",
        contentType: "text/markdown",
      },
    ],
  );
  assert.match(attachments[0].objectKey, /^p_[0-9a-f-]{36}$/);
  assert.match(attachments[1].objectKey, /^[0-9a-f-]{36}\.md$/);
});

test("domestic STS credentials support direct and deployed encrypted response shapes", () => {
  assert.deepEqual(extractOSSCredentials({ result: TEST_CREDENTIALS }), TEST_CREDENTIALS);

  const key = Buffer.from(PUBLIC_CLIENT_CIPHER_CONFIG.key, "utf8");
  const iv = Buffer.from(PUBLIC_CLIENT_CIPHER_CONFIG.iv, "utf8");
  const cipher = crypto.createCipheriv("aes-256-cbc", key, iv);
  const encrypted = Buffer.concat([
    cipher.update(JSON.stringify(TEST_CREDENTIALS), "utf8"),
    cipher.final(),
  ]).toString("base64");
  assert.deepEqual(
    extractOSSCredentials({ result: { data: encrypted } }),
    TEST_CREDENTIALS,
  );
});

test("Aliyun OSS PUT request uses STS signature and a fixed domestic region", () => {
  const request = buildAliyunPutRequest(
    TEST_CREDENTIALS,
    {
      objectKey: "p_demo",
      contentType: "image/png",
      size: 5,
    },
    "Wed, 09 Sep 2026 03:00:00 GMT",
  );
  assert.equal(request.hostname, "demo-bucket.oss-cn-beijing.aliyuncs.com");
  assert.equal(request.path, "/p_demo");
  assert.equal(request.method, "PUT");
  assert.equal(request.headers["Content-Type"], "image/png");
  assert.equal(request.headers["Content-Length"], 5);
  assert.equal(request.headers["x-oss-security-token"], "session-value");
  assert.equal(
    request.headers.Authorization,
    "OSS access-value:vc3Up8csIzDhV33uE9k7EVejG7M=",
  );
});

test("upload keeps short-lived STS values in memory and returns only the OSS key", async () => {
  let requestedBucket;
  let uploaded;
  const attachment = {
    path: "/authorized/reference.png",
    name: "reference.png",
    mediaType: "image",
    bucket: "image",
    contentType: "image/png",
    size: 5,
    objectKey: "p_demo",
  };
  const result = await uploadAttachment(attachment, {
    getCredentials: async (bucket) => {
      requestedBucket = bucket;
      return { result: TEST_CREDENTIALS };
    },
    putObject: async (item, credentials) => {
      uploaded = { item, credentials };
    },
  });
  assert.equal(requestedBucket, "image");
  assert.equal(uploaded.item, attachment);
  assert.deepEqual(uploaded.credentials, TEST_CREDENTIALS);
  assert.deepEqual(result, {
    name: "reference.png",
    mediaType: "image",
    ossKey: "p_demo",
  });
  assert.equal(JSON.stringify(result).includes("secret-value"), false);
  assert.equal(JSON.stringify(result).includes("session-value"), false);
});
