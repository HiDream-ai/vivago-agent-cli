# Delivery playbook

What to do between the terminal event and the user seeing the result.

## Verify before presenting

The remote agent's completion summary is not delivery evidence — verify the file against the
brief:

1. Probe duration and resolution (for example with `ffprobe`) and compare against the requested
   hard constraints.
2. Sample at least one frame per scene; check product appearance against the reference image
   and that no brand marks or garbled generated text appear.
3. Confirm requested captions and voiceover are actually present; transcribe the audio track
   when in doubt.
4. Report any deviation honestly, with remediation options (remote iteration or host-side
   fallback), instead of relaying the remote success report. For image tasks only subject,
   appearance, aspect ratio, and forbidden-content checks apply.

## Local preview

When a successful terminal tool result contains an image, video, or audio `content_id`, create a
local preview before presenting:

```bash
<this-skill-dir>/scripts/vivago-agent --json artifact preview \
  --media-type <image|video|audio> --content-id <content-id>
```

The CLI chooses a unique temporary directory and the correct file extension. Use
`artifact download --output <absolute-path>` only when the user wants a durable file at an
explicit location.

## Presentation hierarchy

Present the final deliverable first and alone. Intermediate artifacts — per-scene clips,
storyboard stills, rejected candidates — are available on request; do not preview them all
unprompted. For image Turns with multiple candidates, show all candidates and let the user
choose; do not select on their behalf.

Render the local `path` with whatever local-media mechanism the host actually has: a file-send
or attachment tool when one exists, inline media syntax where the host renders that type. Hosts
differ — some render images but not video or audio; terminal hosts render neither. When the
host cannot display the media inline, do not claim it was shown: state the absolute path,
duration, and size, and offer to open it in the operating system's default player. Do not
embed remote media URLs as the primary preview: host proxy or media handling can make a valid
artifact appear broken.

## Sharing

Prefer the project deep link over the raw media URL:

```bash
<this-skill-dir>/scripts/vivago-agent --json project link \
  --project-id <project-id> \
  --conversation-id <conversation-id>
```

Display the returned `deep_link` unchanged. Do not construct, replace, or infer its origin from
documentation: the CLI selects the correct Web origin from its compiled profile. The deep link
opens the full creative session with its assets; the `artifact url` output carries no context and
is only for users who explicitly ask for the bare media file.

## At the delivery moment

Proactively offer the two next steps the user cannot discover on their own:

- Same-conversation iteration: revisions reuse existing scenes and cost far less than a fresh
  Turn ("want changes? I can revise in this session and reuse the finished shots").
- The project deep link for team review.

Then update the task ledger entry with the final state and the delivered `content_id`.
