# Fixed

- Read an unexpired shared Vivago ticket without creating a lock file, so read-only host sandboxes can run normal project and conversation commands.
- Replaced authentication helper permission tracebacks with one actionable, path-free structured error.
- Made `ask` and `resume` return success only after `RUN_FINISHED`; `RUN_ERROR` now exits 30, while pre-terminal EOF or transport interruption exits 50 with the latest resume cursor in a `stream_error` JSONL record.

Compatibility: successful JSON/JSONL output is unchanged. Consumers that previously treated an unterminated stream or `RUN_ERROR` as success must now handle the documented non-zero exit and resume cursor.

Verification: authentication and stream regressions use red-green unit tests; overseas-development project/history/assets, artifact resolution, mid-stream resume, and same-conversation second Turn were exercised through the installed CLI.
