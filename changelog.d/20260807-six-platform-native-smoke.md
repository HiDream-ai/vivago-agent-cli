### Changed

- Added a manually triggered native smoke matrix for the six supported macOS, Linux, and Windows ARM64/x64 targets. Each runner executes the bundled launcher, verifies the selected binary, build provenance, overseas development profile, and emits a credential-free JSON report.
- Fixed Windows native smoke execution so the verifier passes batch launcher arguments to `cmd.exe` without collapsing the quoted command into a single token.
