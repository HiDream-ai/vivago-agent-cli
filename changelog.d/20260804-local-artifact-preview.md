# Local media artifact preview

Changed: added `artifact preview` so host agents can materialize generated images, videos, and audio in a unique temporary directory with a renderer-safe extension and always use an absolute local preview path. `artifact download` remains available for saving media to an explicit location.

Compatibility: `artifact url` remains available for shareable links. `artifact preview` is additive; explicit downloads still use streaming I/O and refuse to overwrite an existing file.

Verification: covered URL resolution, image preview extension selection, unique local paths, real local byte writes, absolute path metadata, overwrite refusal, authentication independence, and CLI JSON output with red-green unit tests.
