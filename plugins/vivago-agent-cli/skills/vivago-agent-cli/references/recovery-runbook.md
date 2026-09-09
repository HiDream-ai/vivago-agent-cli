# Recovery runbook

Everything about keeping a long Turn alive across shell timeouts, stream interruptions, context
compaction, and host restarts.

## Task ledger

Keep a ledger file in the working directory, `./vivago-tasks.json`, and update it as states
change. The host conversation is not durable storage: a 15-40 minute wait routinely outlives the
context window, and identifiers that lived only in chat are unrecoverable after compaction.

```json
{
  "tasks": [
    {
      "project_id": "6eba0a27be8d40ed9cbe1c75ed526e65",
      "conversation_id": "997a93f4e1274824984e17d9b64d5776",
      "turn_id": "e2a0c4e27e924a4fae2de9b69eca9c4b",
      "last_event_id": "1785851712214-0",
      "state": "running",
      "log": "./vivago-turn-20260806-1.jsonl"
    }
  ]
}
```

Write the entry as soon as the `type=session` record arrives; update `last_event_id` while
streaming and `state` on the terminal event (`finished` / `error` / `cancelled`). At the start
of any VivagoAgent work, check this ledger and offer to resume unfinished Turns before
submitting anything new.

## Background execution for video Turns

Host shell tools enforce per-command timeouts (commonly 2-10 minutes), far below a video Turn's
15-40 minutes, and a foreground stream also freezes the host conversation. Never hold a video
`ask` or `resume` in a foreground shell call. Use the host's background execution mode when it
has one; otherwise start the command detached, appending all JSONL output to a log file:

```bash
nohup <this-skill-dir>/scripts/vivago-agent --jsonl ask \
  --project-id <project-id> --prompt "<brief>" \
  >> ./vivago-turn-<timestamp>.jsonl 2>&1 &
```

Read the `type=session` identifiers from the first line of that file, then poll its tail between
other work to relay milestones and detect the terminal event; keep handling the user's other
requests meanwhile. A command killed by the host's own timeout is a local interruption, not a
remote failure: the Turn keeps running remotely.

## Stream recovery loop

Long video Turns regularly outlive a single SSE connection: the stream may disconnect (exit 50
with a `type=stream_error` record) many times before the terminal event. Treat exit 50 as a
continuation signal.

```bash
<this-skill-dir>/scripts/vivago-agent --jsonl resume \
  --turn-id <turn-id> --last-event-id <event-id>
```

Loop until `RUN_FINISHED` or `RUN_ERROR` is observed, updating `--last-event-id` from each
`stream_error` record and persisting it to the ledger between attempts. De-duplicate received
events by `event_id`. If several consecutive attempts disconnect immediately, keep resuming at a
lower frequency (30 seconds or more between attempts) and tell the user generation is still in
progress. Never resubmit the original prompt.

## Re-entering a session

When a session restarts (user closed the host, context was compacted) and the ledger shows an
unfinished Turn, recover before doing anything else:

1. `history --conversation-id <conversation-id>` — learn the Turn's current state.
2. Still running → continue with `resume --turn-id <turn-id> --last-event-id <saved-cursor>`.
3. Already finished → recover the deliverable `content_id` from the agent's closing message in
   `history` and from `project assets`, then preview and verify as usual. Use `project assets`
   only to validate or recover server-side asset metadata.

Report what was found before submitting anything new; never resubmit the original prompt to
check on a task.

The JSONL file is temporary operational state, not a second transcript store. Delete it after a
terminal event has been processed and the ledger has been reduced to identifiers, cursor, state,
and delivered content IDs. Never copy full server history or prompt text into the ledger.

## PROJECT_CONVERSATION_CONFLICT

If `ask` exits 30 with `PROJECT_CONVERSATION_CONFLICT`, the prompt was never submitted and no
quota was spent; say so explicitly. Two recovery paths: continue a known conversation directly
with `ask --conversation-id <conversation-id>` from the ledger (bypasses project-level
resolution), or create a fresh project with `project create` and resubmit there. Never retry the
same `--project-id`, and never present the conflict as a failed or billed generation.
