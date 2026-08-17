# vivago-agent-cli

English | [简体中文](./README.zh-CN.md)

VivagoAgent's local client and plugin for Codex and Claude Code. The host agent delegates complete tasks to VivagoAgent through the bundled Go CLI. VivagoAgent owns internal tool execution and server-side conversation history; this plugin does not expose business MCP tools or internal skills.

This repository maintains the Go implementation only. `main` is the long-lived source branch.

## How it works

```text
Codex / Claude Code
        ↓
VivagoAgent Plugin Skill
        ↓
Bundled vivago-agent Go CLI
        ↓
VivagoAgent Web REST / SSE API
```

- Default builds connect to the overseas test environment and are intended for development and testing.
- The `prod` build tag connects to the overseas production environment and is used for the public Beta.
- Users cannot switch environments from the command line. Public packages do not support domestic environments.
- CLI requests use `X-Source: cli` while preserving the Web product semantics.
- Complete conversation history stays in VivagoAgent. The local task ledger stores only the IDs, cursors, and state required for recovery.

## Repository layout

```text
cmd/vivago-agent/                       CLI entrypoint, runtime assembly, and doctor
internal/auth/                          Browser login, loopback callback, and system credential stores
internal/client/                        VivagoAgent REST/SSE protocol mapping
internal/cli/                           JSON/JSONL command contract
internal/sse/                           SSE parsing and terminal-state detection
internal/attachment/                    Attachment types and limits
internal/upload/                        Presigned uploads
internal/artifact/                      Artifact URLs, downloads, and local previews
internal/config/                        Dev/prod compile-time profiles
plugin/                                 Shared Go plugin and skill for Codex and Claude Code
scripts/                                Six-platform builds and Marketplace assembly
tests/                                  Release tooling and distribution tests
docs/                                   Designs, gap analyses, and integration notes
changelog.d/                            User-visible change records
```

## Development

Requirements:

- Go 1.25.12, as declared by the toolchain in `go.mod`
- Python 3.11+, used only for cross-platform builds, Marketplace assembly, and official plugin validation; the CLI runtime does not depend on Python

Install development validation dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the development build:

```bash
GOCACHE=/tmp/vivago-agent-cli-go-cache \
  go run ./cmd/vivago-agent --json version

GOCACHE=/tmp/vivago-agent-cli-go-cache \
  go run ./cmd/vivago-agent --json doctor
```

Default builds use the overseas test environment. To check the production compile-time profile:

```bash
GOCACHE=/tmp/vivago-agent-cli-go-cache \
  go test -tags prod ./...
```

Do not add `--env` to the CLI or allow public builds to fall back to test, domestic, or App APIs.

## CLI commands

Authentication:

```bash
vivago-agent --json auth status
vivago-agent --json auth login
vivago-agent --json auth logout
```

`auth login` opens the Vivago login page and uses a random loopback port, a one-time `state`, and a Form POST callback. Credentials are stored in macOS Keychain, Windows Credential Manager, or Linux Secret Service. Only Linux and WSL2 may fall back to a permission-`0600` local file when Secret Service is unavailable.

Projects and tasks:

```bash
vivago-agent --json project create --name "Codex task"
vivago-agent --json project list --page-size 20

vivago-agent --json project link \
  --project-id <project-id> \
  --conversation-id <conversation-id>

vivago-agent --jsonl ask \
  --project-id <project-id> \
  --prompt "Generate a picture of a kitten"

vivago-agent --jsonl ask \
  --conversation-id <conversation-id> \
  --prompt "Continue refining the previous version" \
  --file /absolute/path/reference.png
```

Recovery, cancellation, and history:

```bash
vivago-agent --jsonl resume \
  --turn-id <turn-id> \
  --last-event-id <event-id>

vivago-agent --json cancel \
  --conversation-id <conversation-id> \
  --turn-id <turn-id>

vivago-agent --json history --conversation-id <conversation-id>
```

Artifacts:

```bash
vivago-agent --json artifact preview \
  --media-type image --content-id <content-id>

vivago-agent --json artifact download \
  --media-type video --content-id <content-id> \
  --output /absolute/path/result.mp4
```

Machine-readable stdout is a compatibility contract: regular commands emit JSON, streaming commands emit JSONL, and diagnostics go to stderr. A remote task succeeds only after `RUN_FINISHED`. If the stream disconnects, resume with the original `turn_id` and `last_event_id`; do not submit the prompt again.

`project link` does not call the server. It uses the compile-time profile to return the correct Web project link for the build. Plugin documentation must not choose or assemble development and production domains itself.

## Network proxies

Regular API calls, attachment uploads, and artifact downloads all follow the standard `HTTP_PROXY`, `HTTPS_PROXY`,
and `NO_PROXY` environment variables. Requests connect directly when no proxy applies, use the configured proxy when
one applies, and connect directly for targets matched by `NO_PROXY`. For example:

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export NO_PROXY=127.0.0.1,localhost
```

Set the variables before launching or restarting Codex or Claude Code from the same terminal. The CLI does not save
proxy addresses or credentials in task state, logs, or the repository. This version does not automatically read OS
proxy settings, PAC files, or third-party proxy app settings. TUN and VPN modes are handled by the operating system and
do not require separate CLI configuration.

## Install the public Beta

Plugin brand assets and color specifications are documented in
[`plugin/assets/README.md`](plugin/assets/README.md).

The public Beta is installed from the `marketplace` branch of the company GitHub repository. It bundles ARM64 and x64 binaries for macOS, Linux, and Windows. Users do not need to install Go, Python, `vivago-agent`, or `vivago-client` separately.

Codex:

```bash
codex plugin marketplace add \
  https://github.com/HiDream-ai/vivago-agent-cli.git \
  --ref marketplace
codex plugin add vivago-agent-cli@vivago
```

Claude Code:

```bash
claude plugin marketplace add \
  'https://github.com/HiDream-ai/vivago-agent-cli.git#marketplace'
claude plugin install vivago-agent-cli@vivago --scope user
```

After installation, reopen Codex or Claude Code and ask it to use VivagoAgent. The first invocation opens the Vivago login page. Sign in normally; never copy a ticket, refresh token, Cookie, or PAT into the host agent.

To upgrade, refresh the Marketplace first and then update the plugin:

```bash
# Codex
codex plugin marketplace upgrade vivago
codex plugin add vivago-agent-cli@vivago

# Claude Code
claude plugin marketplace update vivago
claude plugin update vivago-agent-cli@vivago --scope user
```

To uninstall:

```bash
codex plugin remove vivago-agent-cli@vivago
codex plugin marketplace remove vivago

claude plugin uninstall vivago-agent-cli@vivago --scope user
claude plugin marketplace remove vivago
```

For upgrades, version-specific rollback, and troubleshooting, see the
[VivagoAgent plugin installation and upgrade guide](docs/vivago-agent-plugin-product-install-guide.md).

## Release process

Checks for pull requests and `main` only build, test, and upload temporary candidate packages; they never change the version installed by users. The public Beta is published manually from a selected `main` commit in the company GitHub repository. The release workflow rebuilds the package and requires native startup on all six platforms, Codex and Claude Code installation lifecycle checks, checksums, an SBOM, environment scanning, and production approval before creating a prerelease and updating the `marketplace` branch. See the
[public Beta release design](docs/plans/2026-08-11-vivago-agent-cli-public-beta-release-design.md) for the complete process.

## Validation

```bash
GOCACHE=/tmp/vivago-agent-cli-go-cache go test ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -tags prod ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -race ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go vet ./...
python -m unittest discover -s tests -v
python /absolute/path/to/plugin-creator/scripts/validate_plugin.py \
  plugin
```

See [Go development Marketplace](docs/go-dev-marketplace.md) for six-platform builds and Marketplace assembly, [Go public Beta design](docs/plans/2026-08-07-vivago-agent-cli-go-public-beta-design.md) for the complete public Beta design, and [GA gap analysis](docs/plans/2026-08-07-vivago-agent-cli-public-ga-gap-analysis.md) for the remaining work before general availability.

## Security boundaries

- Never print access tickets, refresh tokens, Cookies, Authorization headers, or presigned upload URLs.
- Do not call VivagoAgent App APIs or expose internal business MCP tools.
- Do not copy complete conversations or user files into a second local store.
- Upload only local paths explicitly authorized by the user.
- Development and production builds use different service URLs and credential namespaces.
- Public plugins must be released through the controlled company GitHub build, validation, and real-environment verification process.

## License and security

Source code is licensed under the [Apache License 2.0](LICENSE). Release packages also include `LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES.md`, an SPDX 2.3 SBOM, SHA256 checksums, and GitHub build provenance.

Report security issues privately through GitHub as described in the [Security Policy](SECURITY.md). Do not post credentials, user content, internal addresses, or exploit details in a public issue.
