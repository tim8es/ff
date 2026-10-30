# FF voice cloning: RU + EN (private-reference contract)

FF provides two interchangeable voice-identity strategies. This uses the `scripts.tts` CLI and the existing WAV + `.voice.json` contract; the video renderer and QA code need no edits.

**The user's voice is not in this repository.** Do not commit, upload to a public Actions artifact, place in a public URL or use a personal reference in a public workflow run. Testing only uses a temporary **synthetic Piper voice** created on the runner. Cloned audio itself also reveals biometric characteristics, so treat final WAV and receipt as private until the user explicitly approves publication.

## Strategies

| Language | Base TTS provider | `tts.voice_conversion` | Model |
| --- | --- | --- | --- |
| Russian/English | `qwen_clone` | omitted | Qwen3-TTS-12Hz-0.6B-Base, cloning directly from a reference |
| English | `kokoro` | `chatterbox` | Kokoro-82M + Resemble ChatterboxVC |
| Russian | `piper` | `chatterbox` | Piper Russian voice + Resemble ChatterboxVC |

Kokoro-82M itself **cannot clone** an arbitrary person from an audio reference. Voice conversion is a separate neural stage and may harm pronunciation or intonation. Qwen3 can transfer an English or Russian reference across languages but may preserve accent. Do not promise identical voice on both languages until subjective listening confirms it.

## Basic usage

Environment variables keep the personal audio path and transcript out of episode manifests:

```bash
export FF_VOICE_REFERENCE=/private/path/my_voice.wav
export FF_VOICE_REFERENCE_TEXT='Exact words spoken in that sample'
python -m scripts.tts --provider qwen_clone --language ru --text-file episode_ru.txt --output ru.wav
python -m scripts.tts --provider qwen_clone --language en --text-file episode_en.txt --output en.wav
python -m scripts.tts --provider kokoro --voice-conversion chatterbox --language en --text-file episode_en.txt --output kokoro_convert.wav
python -m scripts.tts --provider piper --voice-conversion chatterbox --language ru --text-file episode_ru.txt --output piper_convert.wav
```

`--reference-audio` and `--reference-text-file` are also supported. Qwen3 **requires** an accurate reference transcript; ChatterboxVC only needs a reference WAV. Reference duration must be 3–30 seconds with speech. Never fall back silently to a different speaker. Export remains mono 48 kHz PCM WAV with engine, conversion stage and SHA256 in a `.voice.json` receipt; reference bytes or text are not copied into the receipt.

Manifest examples, with the audio location set through an environment variable or private CLI input:

```json
{"language":"ru", "tts":{"provider":"qwen_clone"}, "scenes":[...]}
```
```json
{"language":"en", "tts":{"provider":"kokoro", "voice":"af_heart", "voice_conversion":"chatterbox"}, "scenes":[...]}
```

For a Russian conversion use `provider=piper`. Do not use `provider=kokoro` for Russian; this adapter only supports English Kokoro.

## Dependencies and costs

Heavy dependencies are *optional* and are not loaded by the standard FF renderer/CI tests. Install `qwen-tts` with CPU PyTorch for Qwen cloning; for voice conversion install the upstream `chatterbox-tts` and a base TTS library (Kokoro or Piper). The source adapts the model's public API rather than reimplementing the neural networks. CPU-only inference may be too slow for production, and hosted runners' memory, bandwidth and storage are limited. No external paid synthesis service is used. `qwen_clone` uses the 0.6B **Base**, not the CustomVoice checkpoint.

Model license: Qwen3-TTS Base weights [Apache-2.0](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base); Kokoro-82M [Apache-2.0](https://huggingface.co/hexgrad/Kokoro-82M); Resemble Chatterbox [MIT](https://github.com/resemble-ai/chatterbox); Piper is GPL-3.0 code and model voice licenses vary. Verify exact voice license before monetization. Only clone voices with explicit permission.

## Nonpersonal CI / acceptance

`voice-clone-smoke.yml` generates a synthetic Piper reference on the runner and attempts to synthesize the *same two English and Russian snippets* through Qwen clone and through Kokoro/Piper followed by Chatterbox conversion. Its artifact is a **synthetic example only**, not evidence of a clone of the user's voice. Personal voice intake on a public GitHub-hosted runner is NOT implemented: a separate private handoff must be validated before submitting the user's own reference. No personal sample may enter this workflow through repository files or workflow inputs. Logs/Actions artifacts must not contain original human voice recordings.
