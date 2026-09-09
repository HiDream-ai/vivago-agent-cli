# WorkBuddy ecosystem integration assessment

Date: 2026-09-08

## Background

The existing VivagoAgent product is distributed as a cross-platform Go CLI bundled with host-specific
Skills. It delegates coarse-grained creative and production tasks to the remote VivagoAgent service
without exposing private business tools.

## User requirement

Assess how to make VivagoAgent available to all users in the WorkBuddy ecosystem, including whether
the product should be published as a Skill or an Expert, whether the current CLI-based architecture
can be adapted, and whether its non-standard browser login is likely to satisfy WorkBuddy publication
and security review.

The first marketplace release targets the domestic WorkBuddy ecosystem and the Gouda Agent service.
The domestic and overseas sites expose the CLI browser-login flow at different public paths, so the
WorkBuddy package must use the domestic path rather than copying the overseas URL verbatim.

## Accepted decisions

- The first WorkBuddy release should be a standalone Skill, which is the simplest user-installable
  asset exposed by the WorkBuddy Skill Marketplace.
- Do not reuse or distribute the existing Go CLI or its per-platform binaries in WorkBuddy. Build the
  WorkBuddy integration as a standalone Skill with one portable Node.js script runtime and no
  platform-specific package variants.
- Preserve the existing VivagoAgent browser login page, loopback callback, ticket, and refresh-token
  flow for the first WorkBuddy release. A standards-based OAuth migration is explicitly deferred
  because it is outside the available delivery capacity.
- The domestic production site already implements the dedicated CLI login protocol at `/login`.
  The deployed page validates `client`, `callback_port`, and `state`, rejects caller-provided callback
  URLs, and posts the ticket, refresh token, and state to `http://127.0.0.1:<port>/callback`. A live
  loopback check confirmed that all three expected values were returned without printing or persisting
  credentials. Do not add a new domestic `/agent/login` page or count it as required development work.
- The overseas production site exposes the corresponding page at `/agent/login`. Its deployed
  JavaScript contains the same parameter validation and loopback POST implementation. Current
  verification confirmed the live login page and deployed callback code, but did not complete a fresh
  overseas-account callback, so current end-to-end status remains to be rechecked with a fresh login.
- Build and publish only the domestic Skill in the first release. An overseas WorkBuddy Skill is a
  later package and is not part of the current estimate.
- Keep the domestic release as the self-contained package
  `integrations/workbuddy/gouda-agent/`. A later overseas package belongs at
  `integrations/workbuddy/vivago-agent/`; do not combine the two behind a runtime environment flag
  and do not place either package under the existing `plugin/` release unit.
- The domestic Skill uses fixed production endpoints: the Gouda origin and login page, the existing
  ticket refresh API, and the domestic `oss_key/{image|media}` STS route. It must not call the
  overseas `google_key` upload contract.
- Keep the domestic WorkBuddy Skill behaviorally aligned with the existing CLI Skill. Preserve one
  end-to-end Skill with the same progressive reference topics for brief construction, capability
  limits, output parsing, recovery, and delivery; adapt only the runtime commands, authentication,
  state ownership, upload protocol, and public resource domains for the domestic Node client.
- Do not copy the Codex-specific `agents/openai.yaml` metadata into the WorkBuddy package. Add
  account asset recovery and safe local artifact preview/download to the Node runtime so the aligned
  delivery and recovery instructions describe commands that actually exist.
- Keep every document shipped inside the public `gouda-agent` marketplace package domestic-only.
  State the Gouda endpoints and Aliyun OSS behavior directly; do not mention or compare other-region
  domains, endpoint names, or upload protocols in user-facing Skill documentation. Cross-region
  packaging decisions may remain in internal repository design records outside the ZIP.
- The WorkBuddy uploader accepts only files at the Skill root or in one second-level directory.
  Keep Node runtime modules directly under `scripts/`, reject deeper paths during local validation,
  and regression-test every generated ZIP against the same depth limit.
- Use a stronger marketplace-facing Chinese capability introduction that presents Gouda Agent as an
  end-to-end AI creative production engine, while keeping the separate routing description factual
  and narrowly scoped for reliable Skill selection.
- Treat media-key URL expansion as a regional profile responsibility. The domestic package uses the
  current domestic image-CDN and media-CDN hosts; the later overseas package will use its separate
  storage and media hosts.
- New Project requests now use project `version=v3`. Apply this to the existing Go CLI as well as the
  new WorkBuddy Skill so the clients do not create different project types.
- Domestic WorkBuddy Project deep links use the Gouda site's top-level `/new-chat` route. Do not copy
  the separate `/agent/new-chat` route shape into this Skill.
- Use an isolated WorkBuddy credential and state namespace. Local state is limited to project,
  conversation, turn, cursor, status, and timestamps; it must not duplicate prompts or conversation
  history.
- The assessment must still distinguish a WorkBuddy Skill, Expert, and Connector, but the latter two
  are not first-release requirements.
- Publication approval must not be claimed in advance; the assessment should identify documented
  compatibility requirements, security gaps, and the evidence needed for a formal review.

## Explicit non-goals

- Do not expose VivagoAgent's private business MCP tools or internal Skills.
- Do not move conversation transcript ownership from VivagoAgent to the local WorkBuddy package.
- Do not add domestic or runtime-selectable environments to the public CLI.
- Do not require a WorkBuddy Expert, MCP Connector, Go CLI, native binary, or standard OAuth migration
  for the first Skill submission.
- Do not treat a packaging prototype or local test as proof of WorkBuddy marketplace approval.
- Do not include credentials, user data, private service locations, or operational identifiers in this
  record.
- Do not add backend support for a new persisted `workbuddy` source label in the first release; the
  existing recognized CLI compatibility label may be used until source attribution is changed as a
  separate server task.
