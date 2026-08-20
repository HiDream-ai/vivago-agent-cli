# Distribution

- Publish development Marketplace branches as parentless current-version snapshots protected by an
  exact Git lease, preventing bundled multi-platform binary history from growing on every release.
- Allow a development release to resume the Marketplace step only when the existing immutable Tag,
  Prerelease, source revision, and archive digest all match the candidate.
- Keep plugin installation commands and the six-platform self-contained package unchanged; verified
  with local Git integration, release-resume, and workflow contract tests.
- Verify the snapshot publisher in both channels: two development Prereleases and public
  `v0.3.0-beta.2` all passed their release gates, while the production Marketplace stayed at one
  parentless commit and exactly the same reachable Blob size as `beta.1`.
- Verify the real `beta.1` to `beta.2` Codex install/upgrade/rollback/re-upgrade path and a production
  attachment, SSE image-generation, preview, and download smoke using one-time access only.
