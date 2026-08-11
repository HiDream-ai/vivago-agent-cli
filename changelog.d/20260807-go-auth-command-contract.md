## Added

- Add the Go machine-readable `auth login`, `auth status`, and `auth logout` command contract behind an injectable authentication runtime.
- Add explicit credential-store selection: macOS requires Keychain, Windows requires Credential Manager, and only Linux/WSL may fall back to a private file.

## Security

- Authentication command failures return stable redacted errors instead of forwarding backend errors or credential-bearing values to stdout.
