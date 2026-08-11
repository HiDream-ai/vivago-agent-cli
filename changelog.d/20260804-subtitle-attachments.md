# Added

- Added `.srt`, `.vtt`, `.ass`, and `.ssa` to `ask --file` as document attachments.
- Kept subtitles on the existing Web upload and AG-UI `document` path, including the 1 MiB per-file limit, four-document request limit, and one-document-per-extension rule.

Compatibility: the change is additive; existing attachment mappings and machine-readable output are unchanged.

Verification: added a red-green unit regression for all four subtitle formats and their upload MIME types, OSS-key suffixes, and AG-UI document mapping.
