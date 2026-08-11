# Repository instructions

This repository contains the Go VivagoAgent CLI and the Codex/Claude Code plugin bundle.

## Product boundary

- The host agent delegates coarse-grained work to VivagoAgent through the bundled Go CLI.
- Business MCP tools and internal skills stay behind VivagoAgent and are never exposed by this plugin.
- Conversation and turn history are owned by VivagoAgent. Local code may persist identifiers, cursors, and task states for recovery, but must not create a second transcript store.
- The default Go build targets overseas development; `-tags prod` targets overseas production. Do not add runtime environment switching or domestic/App fallbacks.
- Login uses the dedicated `/agent/login` page and a loopback Form POST callback. Authentication stays behind an `AuthProvider` boundary so standard OAuth can replace it later.
- Hosted MCP and MCP Tasks/MRTR are later transport options, not public Beta dependencies.

## Engineering rules

- Go 1.25.12 or newer. Python 3.11 or newer is used only for build, distribution, and official plugin validation tooling; install `requirements-dev.txt` for the validator.
- Add or change tests before production behavior.
- Never print access tickets, refresh tokens, cookies, presigned URLs, or authorization headers.
- Machine-readable stdout is a compatibility contract. Diagnostics belong on stderr.
- Keep entrypoints and runtime assembly under `cmd/vivago-agent/`.
- Keep protocol mapping in `internal/client/`, authentication in `internal/auth/`, host-facing command handling in `internal/cli/`, and compile-time profiles in `internal/config/`.
- Keep the installable Go plugin source under `plugin/`. Generated binaries and assembled marketplaces do not belong on the source branch.
- Update `docs/plans/2026-08-07-vivago-agent-cli-go-public-beta-design.md` when architectural decisions change.
- Record user-visible changes as one Markdown fragment under `changelog.d/`.
- Maintain a privacy-safe requirement and decision summary under `historical_prompts/` whenever the user confirms a new product requirement, changes product scope, or accepts an architectural decision. Do this as part of the same task before claiming completion; do not wait for a separate reminder.
- Historical prompt records are curated summaries, not chat transcripts. Use one dated Markdown file per coherent requirement thread, update that file while the same thread is active, and include: background, user requirement, accepted decisions, and explicit non-goals. Do not copy credentials, account details, customer data, private URLs, tokens, project/conversation/turn IDs, local paths, or unrelated conversation.
- Before finishing a task, inspect the current change and either update the relevant `historical_prompts/` record or confirm that the task introduced no new product requirement, scope change, or architectural decision. Avoid duplicate records when an existing file already covers the same decision.

## Commands

Run these commands from the repository root:

```bash
GOCACHE=/tmp/vivago-agent-cli-go-cache go test ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -tags prod ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -race ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go vet ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go run ./cmd/vivago-agent --json version
python -m unittest tests.test_go_build_matrix tests.test_go_distribution -v
python /absolute/path/to/plugin-creator/scripts/validate_plugin.py plugin
```

## Definition of done

- Default and `prod` Go tests pass from a clean shell command.
- Relevant race, vet, and distribution tests pass.
- Both plugin manifests are valid JSON and contain no placeholder values.
- The Codex plugin template passes the official local validator.
- README commands match the implemented Go CLI.
- No secret-bearing output appears in tests, fixtures, docs, or logs.
- Confirmed product requirements and architectural decisions are reflected in a privacy-safe `historical_prompts/` summary.
