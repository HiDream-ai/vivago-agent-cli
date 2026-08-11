# Validation

- Record the `0.3.0-dev.8` pre-production closure: authentication refresh, logout and browser
  re-login, Codex model-driven Skill selection, and shared Web project visibility passed on
  macOS ARM64 against the overseas test environment.
- Establish the company `production-beta` Environment with a company-`main` deployment policy.
  The current private-repository GitHub plan does not support required reviewers, so repository
  write access and the manual release workflow remain the temporary authorization boundary.
- Keep production validation and Beta publication blocked until production `/agent/login` is
  deployed. Claude Code model-driven selection is not part of this validation batch.

Compatibility: no CLI command, protocol, package, or runtime behavior changed.

Verification: the released dev.8 launcher completed the authentication checks and one Codex-
selected text task; the same project and response were visible in the overseas-test Web UI, and
the GitHub Environment API confirmed the company-`main` deployment restriction.
