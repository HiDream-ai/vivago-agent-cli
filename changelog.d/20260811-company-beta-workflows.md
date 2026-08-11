# CI

- Bind development jobs to the personal GitHub repository and add company-only read-only Beta
  checks plus a manually approved production Beta prerelease workflow that rebuilds from `main`
  and updates only `marketplace`.
- Run the production Beta launcher on all six supported native runner targets and reject packages
  whose compiled profile, release channel, source revision, or platform does not match the release.
