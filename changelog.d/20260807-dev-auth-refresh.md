# Added

- Add a hidden development-build `auth refresh` command for overseas-test refresh API and credential-store write-back verification.
- Reuse the automatic refresh lock, retry, rejected-credential cleanup, and persistence path even when the current ticket is still valid.

# Security

- Return only `refreshed` and credential backend metadata; never expose tickets, refresh tokens, or authorization headers.
- Reject the command in `prod` builds before authentication runtime initialization, so production execution neither reads the credential store nor sends a network request.

Compatibility: normal login, status, logout, request-time automatic refresh, and public Skill commands are unchanged. The development-only command is not advertised by the plugin.

Verification: default and `prod` Go tests, race detection, vet, 58 Python Pilot regressions, six-target builds, checksum verification, and both plugin validators passed. An explicitly approved overseas-test refresh also passed while the previous ticket was still valid; the following auth status and read-only Web request succeeded without recording credentials.
