# Added

- Add Go `artifact url`, `artifact download`, and `artifact preview` command handling.
- Resolve generated media only through the overseas production storage and media host rules.
- Stream downloads to bounded temporary files and publish atomically without overwriting existing paths.

# Security

- Reject untrusted artifact domains, plaintext URLs, unsafe ports, credentials in URLs, cross-host redirects, private DNS answers, and DNS rebinding at connection time.
- Enforce media-specific content types and 100 MiB image, 500 MiB audio, and 5 GiB video limits.
