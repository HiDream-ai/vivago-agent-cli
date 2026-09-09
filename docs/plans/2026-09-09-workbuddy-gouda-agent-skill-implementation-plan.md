# WorkBuddy Gouda Agent Skill implementation plan

Date: 2026-09-09

## Phase 1: freeze contracts

- Update the existing Go CLI project-create contract test to require `version: "v3"` and observe the
  expected failure before changing production code.
- Add Node contract tests for the fixed domestic profile, project create payload, domestic OSS
  credential route, Aliyun upload, domestic resource URL prefixes, auth callback, and SSE recovery.
- Keep endpoint responses mocked in automated tests; never place live tokens or STS credentials in
  fixtures.

## Phase 2: implement the standalone Skill

- Add the WorkBuddy `SKILL.md`, references, Node entrypoint, and focused standard-library modules.
- Implement JSON/JSONL output, isolated credential/state files, login/refresh, project/conversation
  APIs, account asset recovery, SSE streaming, domestic Aliyun attachment upload, artifact URL
  resolution, bounded preview, and no-overwrite download.
- Preserve the existing CLI Skill's operational reference structure for brief composition,
  capability limits, delivery, output parsing, and recovery. Adapt commands, state ownership,
  authentication, upload, and resource domains to the domestic Node implementation; do not copy the
  Codex-only `agents/openai.yaml` directory.
- Update the Go CLI to create v3 projects and align its bundled Skill instructions.

## Phase 3: validate and package

- Add a Python standard-library validator for the WorkBuddy frontmatter/layout and security rules.
- Add a deterministic Python standard-library ZIP builder whose archive root is `gouda-agent/` and
  whose members do not exceed WorkBuddy's `skill-root/second-level/file` depth limit.
- Run Node tests, targeted and full Go tests, vet/race where relevant, repository release tests, the
  WorkBuddy validator, ZIP inspection, and a secret-pattern scan.

## Phase 4: external verification

- Run a fresh domestic loopback login with the new namespace.
- Run one low-cost domestic v3 project and task E2E, then delete local credentials with logout.
- Import the ZIP into WorkBuddy and verify install, automatic/manual invocation, progress, recovery,
  and final domestic resource links.
- Prepare marketplace copy, icon, version, examples, privacy/data-security disclosure, enterprise
  developer onboarding evidence, and review screenshots in the WorkBuddy publisher console.

Phase 4 contains live account and marketplace operations. It is tracked separately from source-code
completion and is not silently performed by repository tests.
