# FF: MP4 rendering in GitHub Actions

`production.yml` is the **compute backend**, not a publisher. It runs the
existing FF voice generator, Pillow/FFmpeg renderer and technical QA on an
ephemeral Ubuntu CPU runner. The resulting artifact is always
`REVIEW-REQUIRED`. The assistant must inspect and listen to the MP4 and run
the normal semantic QA release gate before presenting it as a finished episode.

## Staging original episode materials

1. Build the fact-checked episode manifest in `work/manifest.json`. Every
   scene needs its matching `image` and `visual_asset` filename, full
   narration, `onscreen_text`, `visual_intent`, `motion_cue`, and duration.
   Use 5–8 scenes, 15–25 seconds total, 2 independent verified sources.
2. Create the original generated imagery in `work/assets/` (at least 3
   genuinely different PNG/JPEG/WebP files). No generated narration, voice
   reference or API token should go in the staging package.
3. Build a text-only package:

   ```bash
   python -m scripts.episode_package --pack work --output staging/episode.zip.b64
   ```

4. Create a temporary Git branch from `main` (for example
   `staging/episode-001`) and commit **only**
   `staging/episode.zip.b64` for public-voice drafts. The package extractor
   validates all entries and rejects path traversal, missing art, duplicate
   image files, unexpected files and oversized packages.

5. In **Actions → FF Actions video preview → Run workflow**, select `main`.
   Set `mode=staged` and `episode_ref=staging/episode-001`.

6. Download the `ff-public-video-REVIEW-REQUIRED` Actions artifact. It
   includes `final.mp4`, `qa.json`, `handoff.json`, the manifest and audio
   provenance. FF's connected GitHub tool can bring this ZIP back into the
   chat, and the ZIP can be extracted into `/mnt/data` for inspection.

## Owner voice (private mode)

When a manifest uses `"tts":{"profile":"ff_owner"}`, select **mode=owner**
rather than `staged`. Add **only the encrypted voice bundle**
`.private_voice/reference.bundle` or its Base64-encoded form
`.private_voice/reference.bundle.b64` to the *same temporary branch* before
running Actions. The repo secret `FF_VOICE_BUNDLE_KEY` must already exist.

Owner mode: decrypts the authorized reference inside the runner, runs Qwen3
1.7B Base on CPU, renders the video, performs technical QA, then encrypts
**the MP4, audio, receipt, manifest and QA report** before artifact upload.
The runner deletes plaintext output even when a job fails. The artifact
`ff-owner-MP4-REVIEW-REQUIRED` contains only `encrypted_video.bundle`:

```bash
export FF_VOICE_BUNDLE_KEY='(your private secret from trusted key storage)'
python -m scripts.production unseal \
  --bundle encrypted_video.bundle --dest /private/ff-review
unset FF_VOICE_BUNDLE_KEY
```

**Never** commit plaintext personal audio, the key or cloned-audio outputs to
a public Git branch. The staging branch can be reset/deleted after successful
download, although Git may retain unreachable encrypted objects for a while.
The encryption protects public artifact access, not against a compromised
runner or privileged repository operators.

## Demo vs release

Run `mode=demo` for an internal sample with five distinct synthetic geometric
test images and short English Piper neural narration. These images, text and
placeholder source URLs are deliberately **not** an actual FF release.

`scripts.production build` always invokes
`scripts.qa.validate(..., technical_only=True)`. This checks script and
voice hashes, duration, frames, sound and codecs without falsely claiming
factual accuracy or artistic quality. It records:

```json
{"status":"TECHNICAL_PREVIEW_REVIEW_REQUIRED","release_ready":false}
```

The assistant must then review the full output for speech clarity, source
accuracy, meaningful motion, generated visual problems, text safe areas, hook,
pacing and ending. Only after review can the standard `scripts.qa` full
release gate run with real reviewer-supplied `review.json`. No automatic
`true` review fields are generated.

## Operational limits

The public GitHub connector can stage a **text** Base64 ZIP, but it cannot
yet reliably call `workflow_dispatch` itself in Chat mode. Starting the
production workflow from its Actions UI is still a manual step. This
limitation is not disguised as a fully hands-off chat pipeline.

The Actions renderer composes **supplied** imagery: it does not generate
pictures or independently research facts, and does not add a music soundtrack
unless one has been deliberately supplied and mixed. Keep the episode assets
and semantic QA owned by the chat agent. The production workflow is a
reproducible, minimal CPU compute and artifact handoff stage, not a complete
creative replacement.


Compact encrypted Opus references are also accepted: the trusted runner decrypts and decodes Opus to temporary PCM WAV before running Qwen3 1.7B. The ciphertext is produced with the same authenticated Fernet key and does **not** expose the sample or transcript in public Git. The full sound output never leaves the runner as plaintext.
