# Known capability limits

What the remote agent cannot do as of this plugin version, and the host-side fallback for each.
Disclose the relevant limit up front when the user's request touches one; never promise an
unsupported step in the brief and silently drop it. This list changes with plugin versions —
trust this file over memory.

## On-screen captions are not burned in

VivagoAgent does not reliably burn caption cards into the delivered video, even when the brief
asks for it. When the user needs captions (performance-ad material almost always does):

1. Say up front that captions will be added by the host after generation.
2. Keep the voiceover lines in the brief; after delivery, transcribe the audio track to get
   per-line timestamps.
3. Burn captions locally with ffmpeg using those timestamps, keeping text inside the platform's
   safe area (avoid the top and bottom UI zones on 9:16 vertical).

## No sound-effect layer

Delivered videos carry voiceover and background music only. Foley and effect sounds (impacts,
ice clinks) named in a brief are not composed. Tell the user, and offer local mixing as a
follow-up when it matters.

## No TTS voice selection

Voice, pacing, and tone of the generated voiceover are not selectable through the brief. If the
user needs a specific voice, set expectations before submitting.

## Handling other unsupported asks

When a brief requirement falls outside the remote agent's capability and no fallback exists,
say so before submitting rather than after delivery. If uncertainty remains about whether a
capability exists, state the uncertainty in the recap and verify the delivered file for it
explicitly (see `delivery-playbook.md`).
