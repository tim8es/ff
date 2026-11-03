# FF: iPhone voice restoration, paced neural edits, stronger hooks

This workflow is private by design. A personal recording, its transcript,
voice embedding, prepared reference or cloned speech must **never** be committed
in plaintext or uploaded as a public artifact.

## Reproducible phone-recording preparation

1. Record on an iPhone Voice Memos application in a quiet furnished room.
   Keep the phone steady approximately 15–25 cm from the speaker, speak slightly
   off-axis, avoid touching the phone, typing, a running fan, traffic and music.
   Read clearly but **do not perform an artificial announcer voice**.
2. Record 60–90 seconds of diverse, natural phonemes (questions, statements,
   numerals, sibilants, quiet/lively phrases). Capture 3–5 seconds of room
   silence separately. Avoid loudness clipping.
3. **Qwen3 Base accepts a reference of 3–30 seconds** with an *exact matching
   transcript*; do not feed the whole long recording. Select a clean,
   15–25-second contiguous passage whose word-for-word transcript is known.
4. On a trusted machine or ephemeral private runner (not a public Git commit):

   ```bash
   python -m scripts.audio_improve private/iPhone.m4a private/reference_clean.wav \
     --start 8.0 --duration 22.0 --strength 0.55
   ```

   Keep the original untouched. The script converts stereo to 24-kHz mono,
   gently filters 75–8500 Hz, estimates stationary background from quiet
   frames, soft-suppresses noise, and normalizes gain without hard gating.
   It cannot perfectly remove room reverberation, keyboard clicks or speech
   contamination. With difficult transient noise, prefer re-recording over
   aggressive suppression.

5. **Audition both original and prepared reference**. Compare consonants,
   breath, vowels and noise at equal perceived loudness. If speech becomes
   metallic or thin, reduce `--strength` to `0.25`, or use the original.
   Do not infer that a cleaner waveform always leads to a better voice clone.
6. Keep the transcript accurate, encrypt the resulting WAV using
   `scripts.voice_secure`, and allow authorized GitHub Actions to decrypt it
   only on an ephemeral runner. `scripts.production` performs the same
   mild cleaning automatically inside owner-mode FF Actions.

## Why FF previously had audible gaps

The old timeline began each fragment 150 ms into a **fixed scene duration**.
The rest of the interval was silence; a 2-second sentence in a 4.8-second
scene left 2.65 seconds of dead air. This is primarily an **editing** problem,
not a voice-model problem.

With `adaptive_pacing=True`, `scripts.tts.generate` uses
`scripts.audio_improve.compose_paced` to softly trim only leading/trailing
silence in each TTS fragment (not consonants or internal pauses). It inserts
~70 ms after the first hook, ~120 ms between subsequent spoken fragments, and
~200 ms at the ending. It returns precise
`receipt.scene_durations`; `scripts.production` writes those timing
values into the manifest before rendering the MP4. No time-stretching or
sentence overlap. The mix should use effects **below** speech.

## The storytelling gate

A new non-demo episode now needs an explicit `story_arc` and 5–8 scenes:

```json
{
  "story_arc": {
    "hook": "Это существо старше динозавров!",
    "evidence": "Линия мечехвостов существует сотни миллионов лет.",
    "reveal": "Древняя линия не означает, что каждый вид остался неизменным.",
    "payoff": "Прошлое живет рядом с нами."
  },
  "scenes": [
    {"beat":"hook","narration":"Это существо старше динозавров!"},
    {"beat":"evidence"},
    {"beat":"evidence"},
    {"beat":"reveal"},
    {"beat":"payoff","narration":"Прошлое живет рядом с нами."}
  ]
}
```

This is a **structure sketch**, not a complete FF manifest: all real scenes
must still include duration, image, visual intent, motion cue, evidence URL,
onscreen text and properly attributed facts. `scripts.story_arc` checks that
the first spoken line **begins** with the hook, evidence and reveal are present,
and the final line includes the payoff. This structural gate cannot measure
actual narrative quality or guarantee retention. Human QA is still mandatory.

## Three measurable hypotheses to test after approval

| Hypothesis | Change | Technical check | Editorial check |
| --- | --- | --- | --- |
| H1: phone noise hurts voice identity | Gentle filtering and optional alternative references | Background/noise at matched speech gain; no clipping | Blind A/B on timbre, clarity and robotic artifacts, with Qwen 1.7B fixed |
| H2: fixed scene lengths create long pauses | Actual speech-driven scene duration | No >0.35 s **between-clip** dead-air gaps; audio/video duration alignment | Does the breathing/phrasing still feel human? |
| H3: low early engagement follows weak hooks | Immediate spoken contradiction and explicit reveal/payoff | First scene narrates hook at time zero, per-shot intent defined | After publication compare viewed-vs-swiped and 3-second retention, not assumed views |

Use the original 31-second iPhone recording to compare cleaning/montage.
A new, longer recording will allow testing multiple distinct 15–25 s
references. **Do not make model 1.7B larger just for a perceived improvement.**

## Air-purifier / fan noise: dedicated opt-in preset

The mild `soft_denoise` is still the FF default. For a stationary air purifier, listen to `fan` and `fan_strong` separately. The new `scripts.audio_fan.fan_reduce` performs high-pass filtering, an **optional narrow notch at a measured appliance tone**, stationary room-tone noise suppression, and (only with `fan_strong`) a soft, smoothed expander for the quietest frames. It does **not** replace Qwen3 TTS or train a new voice.

To reproduce the iPhone recording test (the 894 Hz tone was measured **on this recording**, not a universal fan frequency):

```bash
python -m scripts.audio_improve "/private/iphone.m4a" "/private/fan_balanced.wav" \
  --start 1.08 --duration 29.6 --preset fan \
  --noise-start 0 --noise-duration 0.73 --fan-notch-hz 894

python -m scripts.audio_improve "/private/iphone.m4a" "/private/fan_strong.wav" \
  --start 1.08 --duration 29.6 --preset fan_strong \
  --noise-start 0 --noise-duration 0.73 --fan-notch-hz 894
```

If the original recording starts directly with speech, omit `--noise-start/--noise-duration`: the software selects the quietest 220 ms windows for its noise estimate, which is less precise and must be auditioned. If no narrow frequency peak has been measured, **omit** `--fan-notch-hz`; don't blindly remove 894 Hz from other voices. Typical fan strengths: `--fan-strength 0.65–0.85`. Noise suppression during speech and audible distortion cannot both be optimized perfectly.

A new private episode can select `"tts": {"profile":"ff_owner","reference_preprocessing":"fan","fan_notch_hz":894}`. This setting is opt-in; the historical default `conservative` is unchanged. For a professionally cleaned reference set `reference_preprocessing: "none"` to avoid double filtering. The voice remains ephemeral in the trusted runner, and MP4/voice artifacts must stay encrypted. **Never use an encryption key exposed in public Git history; rotate it before cloning.**

Verify: at equal listening level compare natural vowels, sibilants, plosives and fan tone **during speech**, not only quiet pauses. A silent background can conceal degraded voice identity; Qwen A/B with the same exact transcript is the acceptance test.
