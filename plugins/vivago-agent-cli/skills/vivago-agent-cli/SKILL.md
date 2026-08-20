---
name: vivago-agent-cli
description: Delegate a coarse-grained creative or production task to VivagoAgent, continue or recover a VivagoAgent conversation, cancel an active turn, or read its server-side history. Use when the user explicitly asks VivagoAgent to do work, asks to create images or videos with Vivago, or when VivagoAgent is the requested remote agent. Do not use this skill to expose or enumerate VivagoAgent's internal MCP tools.
---

# VivagoAgent delegation

Use the bundled `<this-skill-dir>/scripts/vivago-agent` launcher as the only integration boundary.
With a native Windows command runner, use the adjacent `vivago-agent.cmd`; POSIX shells, including
Git Bash, use `vivago-agent`.
Resolve `<this-skill-dir>` to the directory containing this `SKILL.md`; in Claude Code this is
`$CLAUDE_SKILL_DIR`. Do not search PATH, ask the user to install a CLI, call VivagoAgent business
MCP tools directly, or invent tool names from streamed events.

The bundled CLI fixes its API, login, and Web endpoints at compile time. Treat CLI-configured
endpoints and returned links as authoritative. Never add runtime environment overrides, rewrite
origins, or fall back to alternate endpoints.

Reply to the user in the language of the user's own messages, regardless of the language of this
document or of the brief submitted to VivagoAgent. Translate VivagoAgent's progress notes,
questions, and errors into the user's language; keep command names, identifiers, and file paths
verbatim.

Detailed procedures live in `references/` next to this file and are part of this skill — read
the relevant file when you reach that moment:

- `references/brief-guide.md` — brief templates for video and image tasks, with a worked example
- `references/recovery-runbook.md` — background execution, the task ledger, stream recovery, re-entry
- `references/output-shapes.md` — canonical JSON output of every command you will parse
- `references/delivery-playbook.md` — verification, presentation, sharing, degraded rendering
- `references/capability-limits.md` — what the remote agent cannot do, and the host-side fallbacks

## Host environment gate

The plugin supports macOS, Linux/WSL2, and Windows on ARM64 and x64, and login requires a usable
default browser. In a web, container, or remote-sandbox session, run `doctor` first; on
`UNSUPPORTED_PLATFORM`, or when no browser can be opened for login, stop and tell the user to
run the task from a local desktop host. Do not degrade to raw API calls.

## Preconditions

1. Run `<this-skill-dir>/scripts/vivago-agent --json doctor`.
2. Run `<this-skill-dir>/scripts/vivago-agent --json auth status`.
3. If not authenticated, run the same command with `auth login`. This intentionally opens the
   existing Vivago browser login; tell the user a browser window is coming. Never request,
   print, or copy the token yourself.

After `auth login` returns, immediately report the outcome to the user and continue the original
task; never leave a login result unannounced. An unexpired cached ticket is read without
creating an auth lock file; login, refresh, and logout require write access to the shared auth
directory — if the CLI reports the auth config is not writable, grant the CLI filesystem access
and retry instead of copying tokens. If the bundled executable is missing, report the plugin
installation as incomplete and ask the user to reinstall; do not substitute curl or a direct
business API call.

Check the task ledger (`./vivago-tasks.json`) for unfinished Turns from earlier sessions and
offer to resume them before submitting anything new (see `references/recovery-runbook.md`).

## Before submitting

- Treat online image search as an explicit per-Turn capability. Add `--image-search` only when
  the user asks VivagoAgent to find online images or visual references, or explicitly authorizes
  online visual-material discovery for the task. It does not enable general-purpose web research
  or guarantee factual web citations. Do not enable it merely because a task creates an image or
  video, and do not silently infer consent from the topic.
- Check the request for the hard constraints a brief needs: total duration, aspect ratio or
  target platform, reference image or source assets, voiceover and caption needs. Ask for
  missing ones in one batched round of questions; never invent hard constraints on the user's
  behalf. When the user declines to specify a value, name the default you will use.
- Treat every video submission as expensive: it consumes real quota and takes 15-40 minutes.
- Give the user a one-message recap of what will be generated — duration, aspect ratio, scene
  count, key content — before submitting, and again before resubmitting after a `RUN_ERROR`.
- Compose the brief per `references/brief-guide.md`. Non-negotiable conventions: storyboard as
  numbered scenes with no timestamps; total duration stated once in the overall prompt;
  appearance lock when a reference image is attached; voiceover lines written out.
- Image tasks skip the video questionnaire entirely — follow the image path in
  `references/brief-guide.md`.

## Start a task

If the user did not provide a Vivago project ID, create a v2 project with a short, non-sensitive name:

```bash
<this-skill-dir>/scripts/vivago-agent --json project create --name "<short name>"
```

Then delegate the task:

```bash
<this-skill-dir>/scripts/vivago-agent --jsonl ask --project-id <project-id> --prompt "<user task>"
```

When the current new Turn needs user-authorized online image or visual-reference discovery, add
the per-Turn flag:

```bash
<this-skill-dir>/scripts/vivago-agent --jsonl ask --project-id <project-id> \
  --image-search --prompt "<user task>"
```

The flag applies only to that newly submitted Turn. Add it again to a later
`ask --conversation-id ...` only if that Turn also needs online visual search. Never add it to
`resume`: resume continues the existing Turn and does not create a new search decision.

Repeat `--file "<authorized-path>"` for each user-authorized local attachment; never place a
local filesystem path inside the prompt as a substitute. Include only paths, URLs, attachments,
or data the user explicitly placed in scope; never append general workspace access. Supported
subtitle attachments are `.srt`, `.vtt`, `.ass`, and `.ssa`; they are sent as `document` content
and share the document count, size, and duplicate-extension limits.

The CLI enforces one conversation per project. If `ask` exits 30 with
`PROJECT_CONVERSATION_CONFLICT`, the prompt was never submitted and no quota was spent — say so
explicitly, then recover per `references/recovery-runbook.md`; never retry the same
`--project-id`.

The first JSONL object has `type=session`. Record `project_id`, `conversation_id`, and `turn_id`
in the task ledger immediately (format in `references/recovery-runbook.md`); identifiers that
live only in the conversation do not survive context compaction or a host restart.

Video Turns must run in the background: host shell timeouts (commonly 2-10 minutes) are far
below a video Turn's 15-40 minutes, and a foreground stream also freezes the host conversation.
Use the host's background execution mode, or the detached log-file pattern in
`references/recovery-runbook.md`. A command killed by the host's own timeout is a local
interruption, not a remote failure. Image-scale Turns (about a minute) may run in the foreground.

Immediately after submitting a video task, tell the user it is running and give the expected
range (a short multi-shot video typically takes 15-40 minutes).

## While it runs

- Relay milestone events — storyboard done, clip x of y, composition started — as one-line
  updates at each phase transition; a long Turn must not go silent between submission and
  delivery. Do not forward raw events, tool names, or repeated snapshots.
- Watch `TEXT_MESSAGE_CONTENT` events for a question addressed to the user and surface it the
  moment it is observed — an unanswered question silently stalls the Turn. Never answer on the
  user's behalf; after the user replies, send the answer as a new Turn in the same conversation.
- When the user asks for status, answer from the latest observed event: last milestone, elapsed
  time, remaining expected range. Never open a new Turn, resubmit the prompt, or `cancel` to
  check progress.
- If the user changes requirements mid-run, ask one question before acting: does the change
  invalidate the current deliverable? Cancel (with the user's confirmation) and resubmit only
  then; otherwise let the Turn finish and iterate. State the trade-off — cancelling stops
  further quota spend but discards unfinished work. Never cancel on your own initiative.

## Deliver

Verify before presenting: probe duration and resolution against the brief, sample one frame per
scene, confirm requested captions and voiceover are present. The remote agent's own completion
summary is not delivery evidence; report deviations honestly with remediation options.
Checklist in `references/delivery-playbook.md`.

Create a local preview for every media artifact before presenting it:

```bash
<this-skill-dir>/scripts/vivago-agent --json artifact preview \
  --media-type <image|video|audio> --content-id <content-id>
```

Present the final deliverable first; intermediate clips and stills only on request. If the host
cannot render the media inline, say so and give the local path — do not claim it was shown
(degraded modes in `references/delivery-playbook.md`). Share results with the project deep link,
not the raw media URL (format in `references/delivery-playbook.md`).

At delivery, proactively offer the next steps: same-conversation iteration reusing existing
scenes, and the deep link for team review. Then update the ledger entry with the final state.

## Continue, recover, cancel

- Iterate in the same conversation with `ask --conversation-id <conversation-id>`, naming the
  reusable shots from earlier Turns; do not create a new project for a revision.
- Exit 50 is a continuation signal, not a failure: the remote Turn keeps running. Resume in a
  loop with the persisted cursor per `references/recovery-runbook.md`; never resubmit the
  original prompt.
- When re-entering a session that had an unfinished Turn, recover from the ledger first: run
  `history --conversation-id <conversation-id>` to learn the Turn's state, then resume it or
  recover the finished artifact — full runbook in `references/recovery-runbook.md`.
- `cancel` only when the user requests it, and treat it as asynchronous: acknowledged, not
  instant. Report the task as stopped only after the terminal event arrives; quota already spent
  on generated shots is not returned.
- Read server-owned history with `history --conversation-id <conversation-id>`. The local plugin
  does not maintain a second transcript store; the ledger holds identifiers, cursors, and states
  only.

## Output and errors

Canonical JSON shapes for every command are in `references/output-shapes.md` — parse those
instead of scraping free text.

- Exit `20`: authentication failed; offer `auth login` and tell the user a browser window will open.
- Exit `30`: the remote task failed; relay the structured error and do not retry on your own.
- Exit `40`: local dependency missing; show `doctor` results.
- Exit `50`: stream interrupted while the remote task may still be running; tell the user
  generation continues, then follow the recovery loop.
- Other non-zero exits: report the structured error without claiming the remote task succeeded.

Known capability limits — no caption burning, no sound-effect layer, no TTS voice selection —
and their host-side fallbacks are listed in `references/capability-limits.md`. Disclose the
relevant limit up front when the user asks for one of these; never promise an unsupported step
in the prompt and silently drop it.

Never expose Authorization headers, tickets, refresh tokens, presigned URLs, or local auth
config contents.
