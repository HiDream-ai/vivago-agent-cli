# Added

- Add repeatable Go `ask --file` support for images, video, audio, documents, and subtitle files.
- Validate all attachment formats, counts, sizes, and regular-file properties before project lookup or upload.
- Request Web upload credentials, stream files to signed HTTPS URLs, and put only storage keys into the chat message.

# Security

- Reject symlinks, directories, devices, changed files, private upload hosts, unsafe URL authority data, proxies, and redirects.
- Keep Authorization on Vivago API requests only and never expose signed upload URLs in chat bodies or machine output.
