# Attribute WorkBuddy Skill traffic independently

- Send `X-Source: workbuddy` on every domestic WorkBuddy Skill API request, including Project APIs
  and SSE conversation calls.
- Keep the existing Go CLI and its Codex/Claude plugin on `X-Source: cli`.
- Update the WorkBuddy API contract, design record, and regression tests for the new source value.
