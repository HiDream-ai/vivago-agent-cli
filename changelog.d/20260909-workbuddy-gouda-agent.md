# WorkBuddy Gouda Agent Skill and v3 projects

- Add an independently packaged domestic WorkBuddy `gouda-agent` Skill implemented with Node.js
  standard-library modules, including browser/loopback login, token refresh, project and conversation
  commands, account asset recovery, SSE recovery, isolated local state, domestic Aliyun OSS
  attachment upload, domestic artifact URL resolution, safe preview, and no-overwrite download.
- Keep the domestic WorkBuddy instructions aligned with the existing CLI Skill's brief, capability,
  recovery, output, and delivery references while using domestic commands and service contracts.
- Provide WorkBuddy marketplace display metadata that positions Gouda Agent as an end-to-end AI
  creative production engine while keeping invocation routing precise.
- Add WorkBuddy package validation, deterministic ZIP tooling, tests, and security/privacy reference
  material without changing the existing Codex/Claude Marketplace release contents; runtime modules
  are flattened under `scripts/` to satisfy WorkBuddy's two-level directory limit.
- Create new projects as `version=v3` from both the existing Go CLI and the WorkBuddy Skill.
- Generate domestic WorkBuddy Project links with Gouda's top-level `/new-chat` route.
