# Output shapes

Canonical JSON shapes the host will parse. Parse these instead of scraping free text. All
`--json` commands return one object; `--jsonl` streams one object per line.

## `ask` / `resume` stream (`--jsonl`)

First record of `ask`:

```json
{"type":"session","conversation_id":"2b0a6e0b4d4e4c35b5c422345ae9ef90","turn_id":"b089fff5cb844ebd9d441096827a91c3"}
```

Each later record is one SSE event:

```json
{"type":"event","event_id":"1785851669079-0","event":"message","data":{"type":"TEXT_MESSAGE_CONTENT","delta":"…"}}
```

`data.type` values observed: `RUN_STARTED`, `TEXT_MESSAGE_START/CONTENT/END`,
`TOOL_CALL_START/END/RESULT`, `ACTIVITY_SNAPSHOT`, `CUSTOM`, and the terminal pair
`RUN_FINISHED` / `RUN_ERROR`. Treat every non-terminal event as progress.

Stream interruption (process exits 50):

```json
{"type":"stream_error","conversation_id":"997a…","turn_id":"e2a0…","last_event_id":"1785851712214-0","error":{"code":"STREAM_ENDED_EARLY","message":"SSE stream ended before RUN_FINISHED or RUN_ERROR; resume the turn with last_event_id"}}
```

## `--json` command envelope

```text
{"ok": true, "data": <command-specific object>, "error": null}
```

`project create`:

```json
{"ok":true,"data":{"code":0,"message":"success","data":{"project_id":"6eba0a27be8d40ed9cbe1c75ed526e65"}},"error":null}
```

`artifact preview`:

```json
{"ok":true,"data":{"path":"/tmp/vivago-agent-preview-xxxx/preview.mp4","bytes":19404802,"content_type":"video/mp4"},"error":null}
```

`artifact url`:

```json
{"ok":true,"data":{"url":"https://media.vivago.ai/<content-id>"},"error":null}
```

`auth status`:

```json
{"ok":true,"data":{"logged_in":true,"backend":"keychain","needs_refresh":false},"error":null}
```

`auth login` returns only the credential backend, never a token; `auth logout` returns
`{"logged_out":true}`. `doctor` reports per-check booleans under `data.checks`, including the
compiled profile and target environment.

`project assets` returns paginated account-level asset groups; each `sub_assets[]` entry
carries a `content_id` and media URLs. Video `content_id`s end in `.mp4`; image content ids are
`p_`-prefixed.

## Where the final deliverable id lives

The final video `content_id` currently appears in the agent's closing message and in
`project assets`, not as a dedicated terminal field. Cross-check both when recovering
artifacts: the stitched final is the `.mp4` content id referenced in the closing summary; the
other `.mp4` entries of the same turn are per-scene clips.
