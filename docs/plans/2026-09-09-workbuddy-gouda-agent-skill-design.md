# WorkBuddy Gouda Agent Skill design

Date: 2026-09-09
Status: approved for implementation

## 1. Goal

Publish Gouda Agent in the domestic WorkBuddy Skill Marketplace as a standalone Skill. The first
release delegates coarse-grained creative and production tasks to the existing domestic
VivagoAgent service while preserving the current browser login, loopback callback, ticket, and
refresh-token flow.

This release does not reuse the Go CLI or distribute any of its six platform binaries. It uses a
single Node.js implementation that is packaged and reviewed independently from the existing Codex
and Claude Code plugins.

The official WorkBuddy format is the source of truth for the package layout:

- https://open.workbuddy.cn/docs/skill
- https://github.com/infometa/workbuddyskills/tree/main/skills/ctrip-wendao

## 2. Repository and release layout

```text
integrations/workbuddy/
├── gouda-agent/                    # domestic marketplace ZIP root
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── gouda-agent.js          # command entrypoint
│   │   ├── artifact.js             # domestic URL resolution and safe download
│   │   ├── auth.js                 # loopback login and refresh
│   │   ├── client.js               # Gouda Agent HTTP/SSE client
│   │   ├── config.js               # fixed domestic production profile
│   │   ├── credentials.js          # isolated private credential store
│   │   ├── oss.js                  # domestic Aliyun OSS STS upload
│   │   ├── output.js               # stable JSON/JSONL output
│   │   ├── sse.js                  # incremental SSE decoder
│   │   └── state.js                # identifiers/cursor/status only
│   └── references/
│       ├── api-contract.md
│       ├── authentication.md
│       ├── brief-guide.md
│       ├── capability-limits.md
│       ├── commands.md
│       ├── delivery-playbook.md
│       ├── output-shapes.md
│       ├── recovery-runbook.md
│       └── security-and-privacy.md
├── tests/
│   └── gouda-agent/                # repository tests, excluded from ZIP
└── tooling/
    ├── package_skill.py             # deterministic ZIP assembly
    └── validate_skill.py            # WorkBuddy structure/security checks
```

The future overseas release will be a second self-contained package at
`integrations/workbuddy/vivago-agent/`. It will not be an environment flag inside `gouda-agent`.
No empty overseas directory is added in the domestic first release.

Only `integrations/workbuddy/gouda-agent/` enters the WorkBuddy ZIP. Tests, packaging tools,
existing `plugin/`, and generated archives stay outside it. Phase one uses a manually generated
ZIP. An independent `workbuddy-skill-release.yml` may be added after the marketplace contract has
stabilized.

WorkBuddy accepts only `skill-root/file` and `skill-root/second-level/file` archive members. Runtime
modules therefore live directly under `scripts/`; a nested `scripts/lib/` directory is invalid. The
repository validator and ZIP tests enforce this maximum depth before upload.

The WorkBuddy Skill preserves the existing CLI Skill's operational structure: `SKILL.md` owns the
end-to-end delegation lifecycle, while brief composition, capability limits, output parsing,
recovery, and delivery are progressively disclosed through the same five reference topics.
Domestic API, authentication, command, and security references remain separate because they are
specific to the WorkBuddy implementation. The Codex-only `agents/openai.yaml` is not copied into the
WorkBuddy package because it is not part of the documented WorkBuddy Skill structure.

## 3. Fixed domestic profile

The Skill has no runtime environment selector and no overseas fallback.

| Purpose | Domestic value |
| --- | --- |
| API and Web origin | `https://goudaai.com` |
| Login page | `https://goudaai.com/login` |
| Token refresh | `GET /prod-api/user/apikey2token` |
| Project create | `POST /api/agent/v1/project/create` |
| Conversation chat | `POST /api/agent/v2/conversation/chat` |
| OSS credentials | `GET /prod-api/user/oss_key/{image|media}` |
| Public image prefix | `https://storage-cdn.hidreamai.com/image/` |
| Public video/audio prefix | `https://media-cdn.hidreamai.com/` |

Project creation always sends `version: "v3"`. The existing Go CLI is changed to the same project
version in this work so the two clients do not create different project types.

`X-Source: cli` remains the compatibility value for this first release because the current server
only recognizes `cli`; arbitrary values are discarded. `User-Agent` and the Skill version identify
the WorkBuddy client operationally. Introducing a persisted `workbuddy` source is a separate server
change and is not required for marketplace v1.

## 4. Runtime commands

The one entrypoint is invoked as `node scripts/gouda-agent.js ...` and exposes only stable
machine-readable output.

```text
auth status | login | refresh | logout
project create | list | detail | assets | link
ask
resume
cancel
history
artifact url | preview | download
state list | show
doctor
```

Ordinary commands write one JSON envelope to stdout. `ask` and `resume` write JSONL: one session
record followed by normalized SSE event records. Diagnostics and the manual login URL go to stderr.
No command prints a ticket, refresh token, Aliyun access key, STS token, authorization header, or
upload URL.

The first release retains the current coarse-grained boundary. It does not expose VivagoAgent's
business MCP tools or internal Skills.

## 5. Login and credential lifecycle

1. Bind an ephemeral TCP listener to `127.0.0.1` only.
2. Generate 32 random bytes and encode them as a URL-safe `state` value.
3. Open
   `https://goudaai.com/login?client=vivago-agent-cli&callback_port=<port>&state=<state>`.
4. Accept exactly one `POST /callback` from a loopback peer with a bounded form body.
5. Constant-time compare the returned state, require both `ticket` and `refresh_token`, then stop
   the callback server.
6. Persist the two values atomically in the WorkBuddy-only data namespace. On POSIX systems the
   directory is mode `0700` and the credential file is mode `0600`. Symlink credential targets are
   rejected.
7. Decode only the ticket expiry claim locally. Refresh shortly before expiry through
   `/prod-api/user/apikey2token`, replacing the ticket atomically. An invalid refresh token clears
   the local credentials and requires login again.

The Skill never asks the user to paste credentials into chat or a shell command. It does not read or
modify the Go CLI keychain/file credentials.

## 6. Domestic attachment upload

Domestic and overseas upload protocols are intentionally separate.

For an authorized local attachment, the domestic Skill:

1. Validates that the path is a regular file, its extension is supported, and its count and size are
   within the existing client limits.
2. Uses bucket category `image` for JPG/JPEG/PNG and `media` for video, audio, document, and subtitle
   files.
3. Calls `GET /prod-api/user/oss_key/{bucket}` with the current bearer ticket.
4. Accepts the domestic STS response fields `AccessKeyId`, `AccessKeySecret`, `SecurityToken`, and
   `BucketName`. The deployed Web response's encrypted public-client envelope is decoded only for
   protocol compatibility; these short-lived values are held in memory and never persisted.
5. Uploads the file directly to the returned domestic Aliyun OSS bucket using an STS-signed HTTPS
   PUT. The object name is generated locally and contains no original directory path.
6. Sends only the resulting OSS key in the VivagoAgent message content.

The overseas endpoint
`/prod-api/user/google_key/{bucket}?filename=...&content_type=...` and its pre-signed PUT contract are
not called by the domestic Skill.

## 7. Resource URL mapping

SSE/history data may return an OSS key rather than a complete URL. URL assembly is profile-owned:

- image key: `https://storage-cdn.hidreamai.com/image/{escaped-key}`; append `.jpg` only when the key
  has no image extension;
- video/audio/document key: `https://media-cdn.hidreamai.com/{escaped-key}`; append `.mp4` only for a
  video key with no extension;
- an already complete HTTPS URL is accepted only when its hostname matches the domestic image or
  media allowlist.

The future overseas sibling will instead use `storage.vivago.ai` and `media.vivago.ai`. It cannot
import the domestic profile or switch it at runtime.

## 8. State and recovery

The local state file stores only project ID, conversation ID, turn ID, last SSE event ID, status,
and timestamps. It never stores prompts, messages, full server responses, artifact bodies, or a
second conversation transcript.

Every `ask` writes the session identifiers before emitting the session record. Each SSE event with
an ID advances the cursor. `RUN_FINISHED` and `RUN_ERROR` write a terminal status. If the stream ends
without a terminal event, the command emits a recoverable `stream_error`; the next invocation uses
`resume --turn-id ... --last-event-id ...` and never resubmits the original prompt.

## 9. Security and marketplace review

The implementation is designed to make review evidence explicit, but marketplace approval cannot
be guaranteed in advance. The main review-sensitive item remains the non-standard browser/loopback
login instead of OAuth.

Controls included in the package:

- fixed HTTPS origins with no user-controlled API host;
- loopback-only callback, random state, constant-time comparison, bounded body, and single use;
- private, atomic, isolated credential storage and complete secret redaction;
- no shell interpolation of prompts or paths;
- validated attachment types/counts/sizes and generated object keys;
- Aliyun upload host validation and no credential persistence;
- strict public artifact host allowlist and escaped OSS key path segments;
- no telemetry, embedded third-party SDK, native executable, post-install hook, or runtime package
  download;
- deterministic ZIP contents and a repository validator that rejects secrets, symlinks, generated
  binaries, excessive directory depth, and files outside the documented Skill layout.

Submission materials should disclose the exact domains contacted, the loopback callback behavior,
credential storage path/permissions, retention behavior, uploaded-file scope, and logout deletion.
The submission must say that authentication reuses the existing Gouda account system and is not
standard OAuth.

## 10. Verification and release gates

The first release is ready for manual WorkBuddy upload only after all of the following pass:

1. Node unit tests for profile isolation, login URL/callback validation, credential permissions and
   redaction, token refresh, project `version=v3`, API headers, SSE parsing/recovery, Aliyun STS
   signing, attachment validation, and domestic resource URL mapping.
2. Go default and `prod` tests covering the CLI project-version change.
3. Repository WorkBuddy validator and deterministic ZIP build.
4. Secret scan of the Skill directory and generated ZIP file list.
5. A fresh domestic login callback smoke test using an isolated WorkBuddy credential namespace.
6. One domestic business E2E: create a v3 project, submit a small task, observe a terminal event,
   resolve a returned OSS key with the domestic prefix, and log out.
7. Manual import into WorkBuddy followed by invocation, long-turn resume, and UI result checks.

Passing local tests and a business E2E proves technical readiness, not Tencent marketplace approval.

## 11. Explicit non-goals

- No Expert, Connector, Buddy application, or public MCP server.
- No Go CLI or native binaries in the WorkBuddy ZIP.
- No overseas fallback or combined domestic/overseas package.
- No OAuth server or account-system redesign.
- No local transcript database.
- No exposure of private business MCP tools or internal Skills.
- No automatic marketplace submission or publication in this implementation task.
