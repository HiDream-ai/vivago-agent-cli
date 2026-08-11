# Changed

- Switched project create/list to VivagoAgent Web v1 routes and added a regression guard that forbids App API routes.
- Added read-only Web project asset listing and deterministic public URL resolution for image, video, and audio content IDs.
- Kept `platform=web` for Web visibility and `X-source: cli` for request-source identification.
- Completed one overseas-development image generation E2E through the installed CLI and server-owned SSE/history flow.

Compatibility: project and artifact commands remain JSON-compatible; new `project assets` and `artifact url` subcommands are additive. App v1 routing is intentionally removed.

Verification: 23 unit tests, Codex plugin validation, live project creation, 53-event SSE generation ending in `RUN_FINISHED`, completed history, and a downloaded 2048×2048 JPEG artifact.
