# Public Beta requirements catch-up

Date: 2026-08-08

## Background

This record catches up the confirmed product requirements and architectural decisions made after
the initial project request. It intentionally summarizes decisions instead of preserving the chat
transcript or operational details.

## User requirement

Evolve the initial VivagoAgent CLI proof of concept into an installable Codex and Claude Code
plugin that external users can run safely, while keeping VivagoAgent as the remote agent and the
owner of server-side conversation history.

## Accepted decisions

### Product and protocol boundary

- The host agent delegates coarse-grained creative and production work through the bundled CLI.
- VivagoAgent business MCP tools and internal skills remain private behind VivagoAgent.
- The CLI uses the existing Web REST and SSE contracts. It must not call App-only endpoints or
  introduce an App fallback.
- VivagoAgent owns Project, Conversation, Turn, and transcript data. Local state is limited to
  identifiers, cursors, and task states needed for recovery.
- CLI requests are attributed with `source=cli` while retaining `platform=web`, so CLI-created
  projects and results remain visible in the Web product.

### CLI and plugin distribution

- The public Beta CLI is implemented in Go and bundled with the Codex and Claude Code plugin.
- Distribution targets macOS, Linux, and Windows on both ARM64 and x64.
- Users install the plugin from GitHub without separately installing a language runtime or CLI.
- Development and local validation use a personal GitHub repository and the overseas test
  environment. Public Beta artifacts move to the company GitHub organization and use only the
  overseas production environment.
- The target environment is fixed at build time. There is no runtime environment switch and no
  domestic-environment build in the public Beta design.
- Development publishing and production publishing remain separate. A development prerelease
  must not be promoted directly as a production artifact.

### Authentication and credential handling

- Login uses the dedicated agent login page and a loopback callback with a random local port and
  request state validation.
- The current login implementation reuses the existing Vivago credential model behind an
  `AuthProvider` boundary. A standard OAuth provider may replace it later without changing the
  host-facing command contract.
- The CLI opens the user's browser for interactive login and never asks the agent to read, copy,
  or print credentials.
- Credentials use the operating-system credential store where available, with a restricted local
  fallback where required. Authentication material must never appear in stdout, logs, fixtures,
  documentation, build artifacts, or hosted test reports.

### Task lifecycle and media handling

- A new task can create a project, submit a Turn, stream SSE progress, recover an interrupted
  stream using the original Turn and cursor, cancel a Turn, and read server-owned history.
- A stream interruption is not treated as permission to resubmit the original prompt.
- Local attachments are uploaded only when explicitly authorized by the user.
- Generated artifacts can be previewed and downloaded locally, while project sharing uses a
  VivagoAgent project link rather than exposing raw or signed media URLs.
- The plugin maintains a small recovery ledger, but it does not create a second transcript store.

### Network visual reference search

- A new Chat Run can explicitly enable VivagoAgent's network image and visual-reference search
  capability through the CLI and plugin skill.
- The capability is opt-in for each new Run. It is not a global default and is not inferred from
  unrelated prompts.
- The CLI maps the option to the Web Chat request's top-level `imageSearchEnabled` field.
- Stream resume requests continue the existing Run and therefore do not resend or alter the
  image-search option.
- Plugin guidance describes this as image or visual-reference search, not as unrestricted general
  Web research.

### Validation and release quality

- Validation covers Go tests, race and vet checks, six native binary targets, distribution
  assembly, checksums, plugin validation, and Codex/Claude Code installation lifecycle checks.
- Local functional validation and hosted cross-platform validation are distinct evidence levels;
  a successful build alone does not prove login, SSE recovery, or media delivery.
- Public Beta release artifacts should be reproducible and accompanied by integrity metadata.
- Production signing, notarization, official marketplace review, Hosted MCP, and standard OAuth
  are follow-up hardening work rather than prerequisites for the first controlled public Beta.

### Branch and repository strategy

- Codeup and the personal development GitHub repository converge on `main` as the long-lived
  source branch. Feature branches are short-lived and removed after integration.
- The personal GitHub `dev-marketplace` branch remains only as the development installation and
  rollback channel until the company Beta pipeline replaces it.
- Production selection remains a compile-time profile decision. There is no permanent `prod`
  source branch; production releases use reviewed commits, protected version tags, and CI.
- Legacy Pilot source and generated release commits are preserved with immutable archive tags
  before the obsolete Codeup branches are deleted.
- The future public company GitHub repository starts from an audited clean Go source snapshot
  rather than mirroring the current repository's full Pilot-bearing history or personal
  development artifacts.
- The personal GitHub CI is the fixed development channel: it builds only overseas-test binaries,
  publishes `v0.3.0-dev.N` prereleases, and updates only `dev-marketplace`.
- The company GitHub CI is the fixed public Beta channel: it rebuilds reviewed company `main`
  commits with the production profile, publishes `v0.3.0-beta.N` prereleases, and updates only
  `marketplace` after protected production approval.
- Push and pull-request checks remain read-only. Development and public Beta publication are both
  explicit manual workflows; a normal push must never publish a user-installable version.
- Release workflows do not accept runtime environment, profile, endpoint, Marketplace name, or
  channel inputs. Repository identity, compile-time profile, version syntax, and environment scans
  fail closed if the wrong workflow is run in the wrong repository.
- Public Beta is fully public: after a short private bootstrap and audit period, the company GitHub
  repository is made public and all existing Vivago users may install the production Beta.
- Tags and Releases are versioned snapshots, not source branches. Company versions use
  `v0.3.0-beta.N`; personal development versions use `v0.3.0-dev.N`.
- Because `v0.3.0-beta.1` has no real previous Beta, its isolated host lifecycle gate may use a
  strictly lower, production-profile package rebuilt from the same source solely as an unpublished
  test fixture. Starting with `v0.3.0-beta.2`, compatibility validation must also use the actual
  previously published Beta; the synthetic fixture does not replace real cross-version evidence.
- Existing company repositories may be inspected read-only for public-repository governance
  conventions, but must not be modified as part of this work. The inspected public repositories do
  not provide a reusable company `CODEOWNERS`, `SECURITY.md`, or `NOTICE` template, so this repository
  starts with neutral contributor attribution and an initial maintainer rule. The company's legal
  copyright identity and permanent ownership team remain explicit pre-publication confirmations.
- A public Beta publish retry may continue after a Release was created but the Marketplace update
  failed only when the immutable tag, source revision, prerelease metadata, and release asset
  digests all match the rebuilt candidate. Conflicting artifacts and retries older than the current
  Marketplace fail closed. The first successful Beta may initialize the output-only Marketplace as
  an orphan branch; later updates remain normal fast-forward commits.
- Production authentication validation pauses while the dedicated production `/agent/login` entry
  is not deployed. An attempted login in that state is an environment blocker rather than evidence
  that the CLI callback contract failed. Repository and CI preparation may continue, but public Beta
  publication remains gated on a fresh production login, status, logout, and re-login validation
  after the entry is deployed.

## Explicit non-goals

- Do not expose VivagoAgent's private MCP tools or internal skills to plugin hosts.
- Do not store a duplicate conversation transcript locally.
- Do not add Hosted MCP or MCP Tasks/MRTR as a dependency of the CLI public Beta.
- Do not support domestic or runtime-selectable environments in the public Beta CLI.
- Do not automatically capture raw Codex or Claude Code conversations in this repository.
- Do not rewrite the shared Codeup or personal GitHub history merely to remove Pilot ancestry.
- Do not store credentials, personal account information, customer content, private service
  locations, or operational identifiers in historical prompt records.
