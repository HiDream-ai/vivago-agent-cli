# Main branch convergence

Changed the long-lived source branch to `main` across Codeup, the personal development GitHub
repository, hosted validation workflow, and operator documentation. Legacy Pilot source and
generated releases are retained through Codeup archive tags instead of permanent Pilot branches;
the personal `dev-marketplace` branch remains available for development installation and rollback.

Compatibility: development release artifacts and existing `v0.3.0-dev.N` tags are unchanged.
Operators must run source and hosted validation workflows from `main` after the migration.

Verification: workflow contract tests cover the `main`-only hosted validation gate, and the
migration validates both remote default branches and all archive tag targets before old branches
are deleted.
