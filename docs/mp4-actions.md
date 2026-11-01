# FF MP4 production on GitHub Actions

The main entrypoint is [Actions video preview](../.github/workflows/production.yml). This builds a *technical preview* (not an approved release) using one manifest, three or more distinct original visual assets, neural speech, H.264/AAC encoding, frame-by-frame checks and a separate handoff report.

## Owner voice (default for user episodes)

In the episode manifest, choose the voice explicitly:

```json
{"language":"ru","tts":{"profile":"ff_owner"},"scenes":[{"image":"scene_01.jpg","visual_asset":"scene_01.jpg","duration":4.8,"narration":"..."}]}
```

`ff_owner` resolves to **Qwen3-TTS 1.7B Base** using the authorized voice recording, not Piper. The repository **does not** store that original recording or its transcript. The runner receives an encrypted `reference.bundle` (or a Base64 representation, `reference.bundle.b64`) in a trusted temporary staging branch. Its decryption key must exist only as repository Actions secret `FF_VOICE_BUNDLE_KEY`. The result MP4 **and cloned WAV** are encrypted into `encrypted_video.bundle` before upload; the workflow removes all plaintext audio/video from the job workspace. Encrypted artifacts have one-day retention. The `scripts.production unseal` subcommand can decrypt the output in a trusted environment.

Never upload plaintext user recordings, cloned audio or private finished MP4 into a **public** GitHub Actions artifact. An admin with workflow and secret access may still access plaintext during authorized runner execution, so never run an unknown contributor's code with this secret.

## Staged episode

1. Create `episode/manifest.json` and original images named `episode/assets/scene_*.jpg`. Verify that images and `visual_asset` names match. Keep exact fact sources in the manifest.
2. Produce a portable textual stage package:

```bash
python -m scripts.episode_package --pack episode --output staging/episode.zip.b64
```

3. Commit *only* the encoded `staging/episode.zip.b64` and the **encrypted** `.private_voice/reference.bundle.b64` to a temporary trusted branch. Do not commit keys or plaintext WAV files.
4. In the main branch's GitHub Actions, select **FF Actions video preview → Run workflow → mode: owner** and pass `episode_ref` equal to the trusted temporary branch. The trusted main workflow composes the MP4; staged branch scripts are never executed by that workflow.
5. Download `ff-owner-MP4-REVIEW-REQUIRED` and decrypt using the key available only on the trusted local/chat side. Review every scene and the full narration before marking it releasable.

`mode: staged` uses public Piper voice and therefore **must not** be used when requesting the FF owner's voice. `mode: demo` produces a synthetic fixture for testing only.

**Automatic review is deliberately not allowed.** `scripts.qa --technical-only` checks codecs, audio provenance, levels, frame decodability and timeline, and returns `release_ready: false`. Someone must separately inspect factual correctness, onscreen text, movement, clipping, and listen to the entire narration before distribution.

## Boundaries

GitHub Actions builds the MP4; it does not generate bespoke image assets on its own. The image-creation stage may run in chat and then be staged. A successful demo artifact is not an editorial-quality episode. The GitHub connector currently does not expose workflow dispatch, so initiating a trusted main-branch job may require an explicit GitHub Actions UI action; avoid bypassing that with an untrusted staging-branch workflow that has access to production secrets.
