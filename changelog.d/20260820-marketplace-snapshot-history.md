# Distribution

- Publish development Marketplace branches as parentless current-version snapshots protected by an
  exact Git lease, preventing bundled multi-platform binary history from growing on every release.
- Allow a development release to resume the Marketplace step only when the existing immutable Tag,
  Prerelease, source revision, and archive digest all match the candidate.
- Keep plugin installation commands and the six-platform self-contained package unchanged; verified
  with local Git integration, release-resume, and workflow contract tests.
- Verify the new development flow through two immutable Prereleases, a 12/12 host lifecycle run, and
  a Marketplace branch that remains one parentless commit; wire the same publisher into Beta code
  without triggering a production release.
