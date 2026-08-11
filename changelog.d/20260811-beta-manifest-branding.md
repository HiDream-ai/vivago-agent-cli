# Beta manifest branding

- Make the source Codex and Claude manifests environment-neutral templates and inject release
  versions during Dev and Beta assembly.
- Use `Vivago Agent CLI` for Codex manifest, Codex Marketplace, and Skill metadata display names in
  both channels, while keeping channel identity in version, Marketplace internal name, build
  profile, and endpoints.
- Fail Beta assembly and independent verification when either manifest has a mismatched version or
  development wording in user-visible name and description fields or Skill guidance.
- Exclude local metadata and interpreter cache files from assembled plugin distributions.
- Make the company GitHub production Beta the primary README and product-guide installation path,
  with verified upgrade, rollback, uninstall, login, and troubleshooting instructions; remove the
  personal development channel from external-user documentation.
- Align both plugin manifest license identifiers with the repository's Apache-2.0 distribution.
- Keep personal Dev and company Beta behavior identical: remove the production-only manual refresh
  restriction, use one neutral Marketplace description, and compare normalized assembled plugins.
- Use Python's cross-platform tar extractor in release workflows so Windows Hosted Runners do not
  interpret drive-letter paths as remote tar hosts.
