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
