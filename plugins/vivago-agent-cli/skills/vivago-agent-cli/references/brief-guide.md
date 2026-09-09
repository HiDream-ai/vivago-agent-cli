# Brief guide

How to turn a user request into a brief VivagoAgent executes well. Read this before composing
any generation prompt.

## Video brief structure

Include, in this order:

1. **Hard constraints, stated once for the whole piece**: total duration in seconds, aspect
   ratio, target platform (for example "a 15-second 9:16 vertical Douyin ad"). The pipeline
   allocates time across scenes from the total; do not repeat timing inside scenes.
2. **A numbered scene list**: "Scene 1", "Scene 2" (场景 1 / 分镜 1). For each scene give the
   frame content, camera motion, and the selling point it must demonstrate — scene content
   only, no per-scene timing.
3. **Appearance lock**: when a reference image is attached, enumerate the product features that
   must not change (color, structure, parts). Example: "light-pink matte body, one-piece pink
   handle, clear lid, clear straw, stainless rim; do not alter color or structure".
4. **Forbidden items**: brand marks, absolute or unverifiable claims, clear human faces, and
   other generation-risk content. Prefer hands, backs, over-shoulder framing for people.
5. **Voiceover lines written out sentence by sentence**, and an explicit statement of whether
   on-screen captions must be burned in (see `capability-limits.md` — the remote agent does not
   reliably burn captions; plan the host-side fallback up front).
6. **Reusable assets**: when iterating in an existing conversation, name the earlier shots that
   may be reused ("the studio beauty shot from the previous Turn may be reused").

## Scene convention — why no timestamps

The storyboard stage splits generation by numbered scene labels. It does not parse time-range
notation: a storyboard written as a global timeline ("0-3s …", "【3-8s】…") silently fails to
control timing. Observed in pilot: a "15 seconds" request written as four time-stamped beats
delivered 20.4 seconds. State the total once in the overall prompt and keep scenes pure.

## Worked example (condensed)

> 15-second 9:16 vertical ad for the tumbler in the attached reference image. Native handheld
> feel, no brand marks, no clear faces; captions will be added by the host afterwards.
> Appearance lock: light-pink matte body, one-piece handle, clear lid and straw, stainless rim.
> Scene 1: dim garage, flames rise around the standing tumbler; slow push-in; contrast of cute
> vs danger. Scene 2: smoke clears, the tumbler is intact; hand pours out whole ice cubes with
> mist (durability, insulation). Scene 3: studio turntable beauty shot, water droplets on the
> body; end frame holds for the tagline. Voiceover: "…" (each line written out).

## Clarification before composing

Ask for missing hard constraints in one batched round. Do not stretch clarification across
multiple rounds, and do not proceed on invented values. If the user declines to choose, state
the default you will apply ("no duration given — I will brief 15 seconds").

## Image tasks — the lightweight path

For an image task, do not apply the video brief structure or ask video-only questions such as
shot lists or duration. Pass the user's description faithfully — subject, style, and aspect
ratio when given; otherwise proceed with reasonable defaults and name them. Expect completion in
about a minute: skip the long-duration notice, wait for the terminal event, and present the
result in the same reply. When the Turn returns multiple candidate images, preview all of them
and let the user choose which to keep or refine; do not select one yourself. Verify against the
brief (subject, appearance lock, aspect ratio, no forbidden content); duration and audio checks
do not apply. Iterate on the delivered result instead of front-loading questions.

If the user explicitly asks for online image references or authorizes online visual-material
discovery, keep that request in the brief and submit the Turn with `--image-search`. The flag is
for image/visual-reference search, not general web research, and is not required merely because
the final deliverable is an image.
