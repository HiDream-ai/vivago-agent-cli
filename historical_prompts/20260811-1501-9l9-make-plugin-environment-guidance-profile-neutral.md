# Make plugin environment guidance profile-neutral

Change ID: `chg-20260811-1501-9l9`

Date: 2026-08-11

## Evidence provenance

Exact user input unavailable.

AI-derived task summary: Review the bundled VivagoAgent Skill for environment-specific guidance,
replace its development/production mapping with profile-neutral compile-time endpoint guidance,
and close out the focused documentation change with traceable validation, commit, and push.

## Background

The CLI already fixes API, login, and Web endpoints through its compiled profile. The shared Skill
must direct host agents to trust those compiled endpoints and returned links without teaching them
how to select between development and production environments.

## User requirement

Use environment-neutral wording in the bundled Skill while retaining the safety rule that host
agents must not add runtime environment switches, rewrite origins, or fall back to other endpoints.

## Accepted decisions

- Keep one shared Skill document for development and production packages.
- Describe API, login, and Web endpoints as compile-time CLI configuration.
- Treat CLI-configured endpoints and returned links as authoritative.
- Remove package-to-environment mappings from the Skill text.

## Explicit non-goals

- Do not change Go profiles, endpoint values, login behavior, project-link construction, or build
  and release workflows.
- Do not introduce runtime environment selection.
- Do not change any VivagoAgent business API behavior.

## Verification

- Passed: official local plugin validator.
- Passed: `git diff --check` for the focused change.
- Passed: environment-specific Skill Markdown literal scan returned no matches.
- Failed: none.
- Not run: Go tests, race, vet, and distribution suites because production behavior did not change.
