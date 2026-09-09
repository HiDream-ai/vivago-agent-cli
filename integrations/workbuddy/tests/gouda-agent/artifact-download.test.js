"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const { ArtifactDownloader } = require("../../gouda-agent/scripts/artifact");

function mediaResponse(body, contentType) {
  return new Response(body, {
    status: 200,
    headers: {
      "content-type": contentType,
      "content-length": String(Buffer.byteLength(body)),
    },
  });
}

test("artifact download uses the domestic CDN and publishes a complete file without overwrite", async (t) => {
  assert.equal(typeof ArtifactDownloader, "function");
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gouda-download-test-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  let request;
  const downloader = new ArtifactDownloader({
    fetchImpl: async (url, options) => {
      request = { url, options };
      return mediaResponse("image-data", "image/jpeg");
    },
  });
  const destination = path.join(root, "result.jpg");

  const result = await downloader.download("image", "p_demo", destination);
  assert.equal(request.url, "https://storage-cdn.hidreamai.com/image/p_demo.jpg");
  assert.equal(request.options.method, "GET");
  assert.equal(request.options.redirect, "error");
  assert.equal(await fs.readFile(destination, "utf8"), "image-data");
  assert.deepEqual(result, {
    path: destination,
    bytes: 10,
    content_type: "image/jpeg",
  });
  await assert.rejects(
    () => downloader.download("image", "p_demo", destination),
    /already exists/i,
  );
});

test("artifact download rejects a mismatched content type without leaving a partial file", async (t) => {
  assert.equal(typeof ArtifactDownloader, "function");
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gouda-download-type-test-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const destination = path.join(root, "result.jpg");
  const downloader = new ArtifactDownloader({
    fetchImpl: async () => mediaResponse("not-an-image", "text/plain"),
  });

  await assert.rejects(
    () => downloader.download("image", "p_demo", destination),
    /content type/i,
  );
  await assert.rejects(() => fs.stat(destination), { code: "ENOENT" });
});

test("artifact download enforces the media size limit without leaving a partial file", async (t) => {
  assert.equal(typeof ArtifactDownloader, "function");
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gouda-download-size-test-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const destination = path.join(root, "result.jpg");
  const downloader = new ArtifactDownloader({
    fetchImpl: async () => mediaResponse("image-data", "image/jpeg"),
    limits: { image: 5 },
  });

  await assert.rejects(
    () => downloader.download("image", "p_demo", destination),
    /size limit/i,
  );
  await assert.rejects(() => fs.stat(destination), { code: "ENOENT" });
});

test("artifact preview creates a uniquely scoped temporary media file", async (t) => {
  assert.equal(typeof ArtifactDownloader, "function");
  const downloader = new ArtifactDownloader({
    fetchImpl: async () => mediaResponse("video-data", "video/mp4"),
  });

  const result = await downloader.preview("video", "result");
  t.after(() => fs.rm(path.dirname(result.path), { recursive: true, force: true }));
  assert.match(path.basename(path.dirname(result.path)), /^gouda-agent-preview-/);
  assert.equal(path.basename(result.path), "preview.mp4");
  assert.equal(await fs.readFile(result.path, "utf8"), "video-data");
});
