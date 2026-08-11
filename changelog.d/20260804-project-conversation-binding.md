# Project/conversation binding guard

- `ask --project-id` now reads the Web project detail before uploading files or opening the SSE stream.
- Projects with no conversation may create the first one; projects with one conversation automatically reuse it.
- Projects that already contain multiple conversations fail with the structured `PROJECT_CONVERSATION_CONFLICT` business code and never create another conversation.
- This is the CLI preflight guard. VivagoAgent still needs a database-level `project_id` uniqueness rule for concurrent and non-CLI callers.
