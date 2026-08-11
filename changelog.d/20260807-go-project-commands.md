## Added

- Add Go `project create` and `project list` JSON command handling with argument validation and stable exit codes.
- Connect project commands to the current build profile, stored authentication provider, and Web REST API.

## Security

- Apply a 60-second total timeout to ordinary JSON API calls while leaving long-running SSE turns without a total task timeout.
- Return redacted HTTP errors and map 401/403 responses to authentication failures without exposing response bodies or authorization headers.
