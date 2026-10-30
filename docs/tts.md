# FF: interchangeable neural speech providers

A single CLI, `scripts/tts.py`, wraps existing upstream Silero, Kokoro, Piper, Edge TTS and Qwen3 voice cloning. The video compositor and QA keep the same WAV/receipt interface; changing providers does not require changing scene rendering code.

## Select a provider

In the episode manifest:

```json
{"language":"en","tts":{"provider":"kokoro","voice":"af_heart"},"scenes":[{"narration":"Example","duration":3}]}
```

Render with `python -m scripts.tts --manifest episode.json --output voice.wav`. To override a provider for just one run, add `--provider piper` (and optionally `--voice en_US-lessac-medium`). The default if no `tts` block is present remains Edge for compatibility. For a stand-alone script: `python -m scripts.tts --provider kokoro --language en --text-file examples/tts_comparison_story.txt --output out/kokoro.wav`.

The CLI generates **PCM WAV 48 kHz, mono** and a matching `voice.voice.json` receipt with engine, model, voice, language, license note, audio hash and transcript hash. For scene-based input the receipt also has `script_sha256` and aligns clips by scene duration with existing `scripts.voice.compose_timeline`. Impossible alignment raises an error instead of clipping speech. `scripts/qa.py` accepts the metadata contract.

## One-minute comparison

[Workflow](../.github/workflows/tts-comparison.yml) runs a 161-word **identical English story** in three independent GitHub-hosted CPU jobs. Each job installs only the needed backend, downloads weights, writes its own WAV and metadata, and uploads a GitHub Actions artifact (retained for 7 days). No GPU, paid provider or tokens are needed. Run it manually in the Actions UI, or push changes to its tracked files. The workflows use `actions/upload-artifact@v4`.

Model mappings:

| Provider | English voice | Russian voice | Typical runtime |
| --- | --- | --- | --- |
| Silero | `v3_en/en_0` | `v5_ru/xenia` | PyTorch CPU |
| Kokoro-82M | `af_heart` | Not supported by this English model | PyTorch CPU |
| Piper | `en_US-lessac-medium` | `ru_RU-irina-medium` | ONNX CPU |
| Edge | `en-US-GuyNeural` | `ru-RU-DmitryNeural` (check availability) | Online |
| Qwen3 clone | private reference file | same reference or separate Russian reference | PyTorch CPU (performance not guaranteed) |

**License warning:** Silero's standard models are CC BY-NC 4.0, so do not use a generated Silero track in a monetized video without an appropriate license. Kokoro weights are Apache 2.0. Piper code is GPL-3.0 and *individual voice models/datasets may have distinct licenses*; check the precise model before commercial use. Edge is an unofficial access path subject to external service availability and terms. Tests and outputs are not auto-published.

References: https://github.com/snakers4/silero-models ; https://huggingface.co/hexgrad/Kokoro-82M ; https://github.com/OHF-Voice/piper1-gpl ; https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium

If model downloads are blocked or synthesis fails, the corresponding job fails **without substituting another voice**. Judge listenability from the actual generated audio; waveform/FFprobe checks are technical, not subjective.

## RU/EN personal voice cloning: Qwen3-TTS 0.6B Base

Qwen3 supports multilingual zero-shot voice cloning, unlike baseline Kokoro-82M.
The existing TTS interface accepts `--provider qwen3_clone`. It uses
`Qwen/Qwen3-TTS-12Hz-0.6B-Base` (Apache-2.0), with a reference sample
**on the same machine running synthesis** and an exact transcript.

Install optional dependencies on that **trusted** machine:

```bash
python -m pip install qwen-tts numpy soundfile
```

Put your own reference in a private local directory **outside the Git repository**
(or under the ignored `private/` directory). Keep the original audio and transcript
private. For a stand-alone Russian test:

```bash
python -m scripts.tts --provider qwen3_clone --language ru \
  --reference /private/samples/my-voice.wav \
  --reference-text-file /private/samples/my-voice.txt \
  --text-file /private/story-ru.txt --output /private/out/ru.wav
```

For English, use `--language en` and an English story. The same reference
may be reused cross-lingually, but accent, identity similarity and intelligibility
are **not guaranteed**. Two references (one per language) can be compared
without retraining. A 3–30-second clean spoken sample is accepted. The
reference transcript must match the recording; incorrect transcript hurts quality.

In a **local-only, uncommitted** scene manifest:

```json
{
  "language": "ru",
  "tts": {
    "provider": "qwen3_clone",
    "reference": "private/my-voice.wav",
    "reference_text_file": "private/my-voice.txt"
  },
  "scenes": ["... normal FF scenes ..."]
}
```

The adapter loads the model once and reuses its reference conditioning for
every scene. Output remains a 48-kHz mono WAV and the existing QA-compatible
`.voice.json` with transcript/audio checksums. No reference audio, reference
transcript, reference file path, or speaker embedding is written to the receipt.

**Privacy / security:** the public `tim8es/ff` repository, its GitHub
Actions run logs, and public build artifacts are **not suitable for private
biometric voice samples or cloned personal audio**. Public GitHub Actions
artifacts can be downloaded by others. Do not feed personal recordings to the
public Actions test. Its CI uses the **official public Qwen demonstration
reference only** and uploads **only demo-generated speech**. Actual personal
cloning requires a trusted local or private execution environment and
private storage/transfer. `.gitignore` reduces accidents but does not prevent
forced commits (`git add -f`), malicious actions, or exposure after committing.

The second approach, Kokoro + RVC voice conversion, requires a trained target
voice model; KokoClone reports a 30–60 minute training job with a GPU for a
larger dataset. It is **not** a drop-in zero-shot replacement, so it has not
been silently enabled or promised. Keep Kokoro for proven existing voices;
Qwen3 for cloned voices, pending acoustic and identity evaluation.

Sources: https://github.com/QwenLM/Qwen3-TTS ;
https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base ;
https://github.com/sheigl/kokoclone .
