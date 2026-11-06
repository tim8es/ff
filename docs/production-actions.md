# FF — video preview and private owner voice (November 2026)

## Two distinct paths, no other channel

**Public draft/demo:** `.github/workflows/production.yml` in `tim8es/ff`
creates only synthetic or Piper TTS previews without any personal voice
reference. Valid inputs: `mode=demo` or `mode=staged` with a public FF
`staging/episode.zip.b64` on a trusted staging ref. An Actions artifact is
a **review-required** public draft, never a publication approval.

**Private `ff_owner` MP4:** The current route uses
`tim8es/voice-engine` (private) with Qwen3-TTS 1.7B Base; the generic
`tim8es/task-runner/.github/workflows/universal.yml` receives only a
random 32-hex job ID. The private worker fetches a persistent encrypted owner
reference and staged encrypted FF scene text/images, generates voice per scene,
verifies its receipt, renders through the pinned PUBLIC FF compositor in
`--voice-mode external`, and uploads only encrypted results to
`ff-video-<job_id>` in a **private Voice Engine Release**.

Authoritative step-by-step staging, secrets and recovery:
`tim8es/voice-engine/docs/FF_UNIVERSAL_PIPELINE.md`.
No n8n/channel B renderer is part of this flow.

## Prepare and stage FF visuals

An FF episode consists of one `manifest.json` and at least three distinct
original visuals under `assets/`. Every scene needs narration, explicit
safe text, meaningful motion, references/evidence and an image ID that
matches `visual_asset`. Sources must be independently verifiable.
The audience-facing video is 15–25s and has 5–8 scenes.

For public **draft** generation only:

```bash
python -m scripts.episode_package --pack /private/ff_episode \
  --output staging/episode.zip.b64
```

The `staged` Actions workflow accepts the public staging ref, uses Piper
for a technical preview, and includes a `qa.json` report. Do not stage
unreleased personal audio, private reference transcripts, keys, or
voice-engine results in this public branch.

For PRIVATE owner voice, make the episode staging package in a trusted
workspace, then encrypt it in the private voice-engine job via
`scripts.ff_prepare_job`. New narration is encrypted, the owner reference
stays reusable, and no new audio upload is required.

## Audio/MP4 integrity gate

For private owner-voice input recovered in a trusted environment:

```bash
python -m scripts.production build --bundle /private/episode.zip.b64 \
  --workspace /private/ff_out --voice-mode external \
  --external-voice /private/voice.wav \
  --external-receipt /private/voice.voice.json
```

The `external` contract rejects a wrong model/profile, changed narration,
inconsistent SHA-256, scene timings, unrelated language or a non-PCM16 WAV.
`scripts.production` renders a vertical H.264/AAC MP4 and writes
`qa.json`, `handoff.json`. Passing technical QA **does not** bypass
the seven semantic/audible/visual review checks in `AGENTS.md`.

The old public `mode=owner`, `FF_VOICE_BUNDLE_KEY` and
`.private_voice/reference.bundle` workflow is **RETIRED** for personal
voice generation. The historical code/commit history may still exist,
but never reuse the formerly exposed key. Never send a personal voice WAV or
plaintext MP4 to public Actions artifacts.

## Operational limitations

The private `FF_JOB_FERNET_KEY` must decrypt the retained owner reference.
If the prior key was lost or compromised, the voice owner needs to provide
one fresh reference recording to create a new encrypted profile; inventing a
new key cannot decrypt old ciphertext. The current ChatGPT GitHub connector
cannot read Actions Secrets or dispatch every workflow; passing synthetic
unit tests does not certify a private end-to-end render.

To deliver a completed file in chat, decrypt the private MP4 only in a
trusted environment, view and listen to the full video and check all QA
requirements. Do not claim a successful user-ready MP4 before doing this.
