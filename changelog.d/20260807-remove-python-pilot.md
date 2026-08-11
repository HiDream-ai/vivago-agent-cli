# Changed

- Remove the legacy Python CLI, private Pilot plugin, Pilot-only build scripts, tests, and local distributions from the Go public Beta source branch.
- Replace the legacy root plugin with the Go plugin and Skill under `plugin/`, making the active source immediately visible from the repository root.
- Rewrite repository development, installation, verification, and directory documentation around the Go implementation.

Compatibility: the Codeup `master` and `pilot-marketplace` branches continue to preserve the Python Pilot source and installable `0.2.0-pilot.3` marketplace for rollback.
