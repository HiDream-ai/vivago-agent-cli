"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { PROFILE } = require("../../gouda-agent/scripts/config");
const { resolveArtifactURL } = require("../../gouda-agent/scripts/artifact");

test("domestic profile is fixed and contains no overseas fallback", () => {
  assert.deepEqual(
    {
      apiBaseURL: PROFILE.apiBaseURL,
      webBaseURL: PROFILE.webBaseURL,
      loginURL: PROFILE.loginURL,
      projectVersion: PROFILE.projectVersion,
      ossCredentialPath: PROFILE.ossCredentialPath,
      imagePrefix: PROFILE.imagePrefix,
      mediaPrefix: PROFILE.mediaPrefix,
    },
    {
      apiBaseURL: "https://goudaai.com",
      webBaseURL: "https://goudaai.com",
      loginURL: "https://goudaai.com/login",
      projectVersion: "v3",
      ossCredentialPath: "/prod-api/user/oss_key",
      imagePrefix: "https://storage-cdn.hidreamai.com/image/",
      mediaPrefix: "https://media-cdn.hidreamai.com/",
    },
  );
  assert.equal(JSON.stringify(PROFILE).includes("vivago.ai"), false);
  assert.equal(Object.isFrozen(PROFILE), true);
});

test("artifact URLs use domestic prefixes and escape path segments", () => {
  assert.equal(
    resolveArtifactURL("image", "folder/p_demo"),
    "https://storage-cdn.hidreamai.com/image/folder/p_demo.jpg",
  );
  assert.equal(
    resolveArtifactURL("image", "folder/p demo.png"),
    "https://storage-cdn.hidreamai.com/image/folder/p%20demo.png",
  );
  assert.equal(
    resolveArtifactURL("video", "folder/result"),
    "https://media-cdn.hidreamai.com/folder/result.mp4",
  );
  assert.equal(
    resolveArtifactURL("audio", "folder/result.mp3"),
    "https://media-cdn.hidreamai.com/folder/result.mp3",
  );
});

test("artifact URL validation rejects traversal and foreign hosts", () => {
  assert.throws(() => resolveArtifactURL("image", "../secret"), /unsafe/i);
  assert.throws(
    () => resolveArtifactURL("video", "https://media.vivago.ai/result.mp4"),
    /not allowed/i,
  );
  assert.equal(
    resolveArtifactURL(
      "image",
      "https://storage-cdn.hidreamai.com/image/p_demo.jpg",
    ),
    "https://storage-cdn.hidreamai.com/image/p_demo.jpg",
  );
});
