---
name: ff-shorts
description: Use when the user asks to create or repeat an FF short video in ChatGPT, especially “Бесполезные факты”, with verified facts, animated scenes, living minimal typography, infographics, and a rendered MP4.
---

# FF Shorts: verified fact to playable video

**Goal:** user supplies a theme or asks for one; return a playable downloadable MP4 **in the same chat**, not a draft or set of stills. Repository `tim8es/ff` is the source of truth. Read root `AGENTS.md` before execution.

## Contract

| Stage | Required output | Fail if |
|---|---|---|
| Research | source-backed fact record | claim unsupported |
| Script | 15–25s hook → explanation → payoff | hook is generic or fact misleading |
| Direction | 5–8 shot timeline | repetitive static scenes |
| Assets | coherent, text-free visual material | AI draws fake diagrams or illegible text |
| Render | verified H.264 9:16 MP4, optional narration/music | only images or renderer hasn't run |
| QA | ffprobe + representative frames | missing asset, bad crops, wrong subtitles |

## Execution

1. Confirm topic implicitly from context; pick a visually demonstrable fact when unspecified. Research quickly and retain the actual URLs in a per-video source manifest (not as fabricated overlaid citations).
2. Choose the final Russian voiceover: ~35–55 words, hook immediately, explanation understandable without prior context, ironic closing. Factcheck after every rewrite.
3. Produce the shot manifest. Use `examples/wombat.json` as a structural reference but avoid repeating its subject/phrasing.
4. Generate cohesive assets using available chat image/video generation. Background illustrations **must not include words, UI, pseudo-text, data labels**, or exaggerated anatomical claims. Only code-driven on-screen typography and infographics should contain exact copy. For a motion-heavy shot, prioritize actual video generation over Ken Burns.
5. Render in the active chat sandbox using `python scripts/render.py project.json --assets ./assets --audio mix.wav --output /mnt/data/ff_<topic>.mp4`. `--audio` is optional. If richer rendering tech is available, use it, while preserving the exact output contract and verify the output.
6. Check stream metadata with ffprobe; extract frames at beginning/middle/end and inspect them. Review frame pacing, crop, text, source accuracy and soundtrack status. Reject silent video described as “voiced” and reject photo-only deliverables.
7. Share direct sandbox MP4 link. Do not require user to execute CLI commands and do not upload or publish on their behalf.

### Rendering notes

- Video defaults to 720×1280, 24fps, H.264; tune after QA. `image` scenes accept an asset filename relative to `--assets` and use subtle moving camera crop. `title`, `sequence`, `compare`, `end` scenes render kinetic typography/vector graphics procedurally.
- The built-in renderer is an **offline fallback**; it does **not** generate actors' body motion, speech or licensed music. Generate those with other chat tools when available.
- For future themes use one file per video for facts/sources/script/scene manifest; keep approved channel style separate from per-video content. Do not store fake engagement metrics or claim a retention guarantee for viewers with ADHD.

### Failure recovery

- Missing video rendering tool: tell the user the current environment lacks rendering; do not show images as a video substitute.
- Generated image has baked text: regenerate a text-free asset or disable duplicate overlay only as a temporary exception.
- Voice generation unavailable: render honest silent/score-only preview; explicitly mark absence of voice.
- Research ambiguous: choose another fact or disclose uncertainty.