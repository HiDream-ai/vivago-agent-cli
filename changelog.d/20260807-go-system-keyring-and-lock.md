## Added

- Connect the Go CLI authentication commands to the current build profile and operating-system credential store.
- Add macOS Keychain, Windows Credential Manager, and Linux Secret Service support through `go-keyring`.
- Add cross-process authentication locks for browser login and token refresh, with separate development and production lock files.

## Security

- Keep macOS and Windows fail-closed when the system credential store is unavailable; only Linux/WSL may use the private file fallback.
- Re-read credentials after acquiring the refresh lock so concurrent Codex and Claude Code processes cannot overwrite a newer ticket.
- Pin the build toolchain to Go 1.25.12 so released binaries do not include the standard-library vulnerabilities present in Go 1.25.6.
