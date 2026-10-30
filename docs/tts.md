# FF: interchangeable neural speech providers

A single CLI, `scripts/tts.py`, wraps existing upstream Silero, Kokoro, Piper and Edge TTS engines. The video compositor and QA keep the same WAV/receipt interface; changing providers does not require changing scene rendering code.

## Select a provider

In the episode manifest:

```json
{"language":"en","tts":{"provider":"kokoro","voice":"af_heart"},"scenes":[{"narration":"Example","duration":3}]}
```

Render with `python -m scripts.tts --manifest episode.json --output voice.wav`. To override a provider for just one run, add `--provider piper` (and optionally `--voice en_US-lessac-medium`). The default if no `tts` block is present remains Edge for compatibility. For a stand-alone script: `python -m scripts.tts --provider kokoro --language en --text-file examples/tts_comparison_story.txt --output out/kokoro.wav`.

The CLI generates **PCM WAV 48 kHz, mono** and a matching `voice.voice.json` receipt with engine, model, voice, language, license note, audio hash and transcript hash. For scene-based input the receipt also has `script_sha256` and aligns clips by scene duration with existing `scripts.voice.compose_timeline`. Impossible alignment raises an error instead of clipping speech. `scripts/qa.py` accepts the metadata contract.

## One-minute comparison

[Workflow](../.github/workflows/tts-comparison.yml) runs a 130-word **identical English story** in three independent GitHub-hosted CPU jobs. Each job installs only the needed backend, downloads weights, writes its own WAV and metadata, and uploads a GitHub Actions artifact (retained for 7 days). No GPU, paid provider or tokens are needed. Run it manually in the Actions UI, or push changes to its tracked files. The workflows use `actions/upload-artifact@v4`.

Model mappings:

| Provider | English voice | Russian voice | Typical runtime |
| --- | --- | --- | --- |
| Silero | `v3_en/en_0` | `v5_ru/xenia` | PyTorch CPU |
| Kokoro-82M | `af_heart` | Not supported by this English model | PyTorch CPU |
| Piper | `en_US-lessac-medium` | `ru_RU-irina-medium` | ONNX CPU |
| Edge | `en-US-GuyNeural` | `ru-RU-DmitryNeural` (check availability) | Online |

**License warning:** Silero's standard models are CC BY-NC 4.0, so do not use a generated Silero track in a monetized video without an appropriate license. Kokoro weights are Apache 2.0. Piper code is GPL-3.0 and *individual voice models/datasets may have distinct licenses*; check the precise model before commercial use. Edge is an unofficial access path subject to external service availability and terms. Tests and outputs are not auto-published.

References: https://github.com/snakers4/silero-models ; https://huggingface.co/hexgrad/Kokoro-82M ; https://github.com/OHF-Voice/piper1-gpl ; https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium

If model downloads are blocked or synthesis fails, the corresponding job fails **without substituting another voice**. Judge listenability from the actual generated audio; waveform/FFprobe checks are technical, not subjective.
