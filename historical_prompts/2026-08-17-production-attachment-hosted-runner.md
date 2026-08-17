# Production attachment validation on a hosted runner

Date: 2026-08-17

## Background

The production Beta candidate passed local authentication, text delegation, Web visibility, and SSE
recovery. Attachment upload was blocked on the current development Mac because its network, VPN, or
proxy route could not reach the object-storage upload endpoint through the hardened direct uploader.
Development and production returned the same upload host, while earlier local and hosted development
validation had succeeded.

## User requirement

Continue production Beta validation on a clean company GitHub Hosted Runner without weakening the CLI
upload security boundary. Store only a short-lived production access ticket in a protected GitHub
Environment Secret and keep the approach safe when the repository becomes public.

## Accepted decisions

- Add a dedicated company-main, manually triggered production attachment smoke Workflow.
- Use the `production-beta` Environment and a short-lived ticket-only secret; never upload a refresh
  token.
- Validate only macOS ARM64 and Codex in this iteration.
- Rebuild the production Marketplace from the exact company-main SHA before the online case.
- Cover attachment recognition, image generation, artifact preview, and artifact download.
- Keep reports privacy-safe and remove the Environment Secret after the run.
- Preserve the current SSRF-hardened upload transport until a clean direct-egress run provides evidence
  for a product change.

## Explicit non-goals

- Do not publish a Beta release, tag, attestation, or Marketplace update in this Workflow.
- Do not run Claude Code or the six-platform online matrix.
- Do not add runtime endpoint or environment switching.
- Do not enable proxy use or relax DNS, TLS, port, or redirect checks in the uploader.
- Do not store production refresh credentials in GitHub.

## Verification

- Passed: exact company-main production Beta rebuild and provenance validation.
- Passed: native macOS ARM64 Codex plugin installation and ticket-only credential load.
- Passed: production attachment upload and recognition, image generation, artifact preview, and
  artifact download.
- Passed: sanitized report contained no service identifiers, credentials, or signed URLs.
- Passed: runner credential cleanup and post-run GitHub Environment Secret deletion.
- Not run: Claude Code model invocation, six-platform online production matrix, and Beta publication.
