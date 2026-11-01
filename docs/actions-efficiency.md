# FF GitHub Actions — minimal efficient workflow policy

**CI**: `.github/workflows/tests.yml` runs unit/renderer checks for relevant source, test, example, or CI changes on pull requests and pushes to `main`. Documentation-only and intermediate experimental branch pushes do not launch redundant checks. The `concurrency` group cancels obsolete CI runs for the same branch/PR; this is safe because CI produces no deliverable. Small pip requirements use `setup-python` cache. It installs FFmpeg only when missing and limits jobs to 10 minutes.

**TTS benchmarks**: `tts-comparison.yml`, `qwen3-clone-smoke.yml`, `voice-conversion-smoke.yml`, `voice-smoke.yml` and `qwen-base-compare.yml` now run only via `workflow_dispatch`, not on source pushes. Each provider's optional dependencies remain isolated; avoid installing all neural frameworks into a single Python environment. Qwen's two languages share one model and cloned-voice prompt in `scripts.qwen_batch` rather than loading both twice. The standard `scripts.tts` CLI, receipts and audio format are unchanged.

**Qwen 0.6B/1.7B comparison**: use Actions workflow **FF - Qwen3 Base 0.6B vs 1.7B** in `demo` mode for published Qwen reference audio or `private` mode for a consented, encrypted voice. In private mode, check that `FF_VOICE_BUNDLE_KEY` and `.private_voice/reference.bundle` are present **before downloading PyTorch**; only encrypted generated outputs are uploaded. `cancel-in-progress` is intentionally **not enabled** for synthesis jobs. Do not record personal voice samples or expose plain derived WAV artifacts in public logs/artifacts.

**Model cache policy**: cache only lightweight test pip dependencies. Do not cache large HF model weights by default: they compete for repository cache quota, model upgrades create multiple huge cache versions, and the benchmark is infrequent. Reconsider only if repeated cold downloads are measured and the storage/cache budget is explicitly approved.

**No permanent runner**: no dedicated server, paid API, Docker infrastructure, or pre-built heavyweight images. GitHub Actions provides disposable CPU inference on demand.

## Acceptance checks

- CI on a source-code PR passes; a documentation-only update should not trigger it.
- A manual/temporary public-demo Qwen batch generates RU + EN WAV in one process with exactly one initialized Qwen model and speaker prompt.
- Every WAV must retain a receipt with `language`, `model`, text checksum and audio checksum; FFmpeg must decode it.
- Attempting to reuse a cloner with a different reference, transcript or model size must fail.
- The private workflow must refuse missing encrypted inputs before large dependency installation; any private artifacts remain encrypted.

These changes optimize run count and avoid redundant model loading, but **do not** mean a full episode MP4 production workflow already exists. The FF content pipeline's visual generation and human/agent QA remain separate release gates.
