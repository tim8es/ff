# FF — Shorts production (source of truth)

**Trigger:** In the ChatGPT project FF, requests like «Создай видео», «Следующий ролик», «FF, ролик про…». Default to selecting a topic autonomously. This file is the **only authoritative workflow and style contract**. Do not copy it into the ChatGPT Project instruction or the Skill.

**Deliverable:** a real vertical 9:16 MP4 with **Russian voice narration**, coherent generated imagery, animated motion graphics, infographic, and sound design, returned **in this chat**. Images, storyboards, silent slideshow videos, or a promise to render later do not satisfy the request.

## Production loop

1. **Discover + verify.** Select one surprising, visually demonstrable, harmless fact; cross-check with at least two independent credible sources, preferably primary research. Keep source URLs and uncertainty with the per-video manifest. Reject myths and risky claims.
2. **Write + direct.** Produce a 15–25-second Russian script (roughly 35–55 words): immediate hook → surprising proof/explanation → witty payoff. Plan 5–8 purposeful shots with timing, focal object, exact screen text, motion, narration and audio cues. Each shot must contribute something new.
3. **Make assets.** Generate a visually coherent set of **text-free** hero images, supporting close-ups, objects and backgrounds; create additional short moving shots where a video generator is available. At least three shots need distinctive illustrated/filmed subject matter; do not use generic empty cards as substitutes. Exact facts, labels and infographics are composited separately in code. Never rely on AI-generated anatomical diagrams without checking them.
4. **Narrate + mix.** Generate a pleasant expressive Russian voice (not monotonous), align pauses and visual beats to the recording; add low-level licensed music and restrained SFX when available. **Narration is required for final release.** If voice production is unavailable, disclose that the full deliverable is blocked; offer a silent preview only if the user explicitly requests one.
5. **Compose + animate.** Create one concise scene manifest with paths/timing/typography/focus/voice cues. Render with the best available chat video tools; use `scripts/render.py` for deterministic overlays and infographic/fallback shots, not as a replacement for generated imagery. Keep text editable and separated from AI images. Export H.264 / yuv420p / AAC MP4 (default 720×1280, 24/30 fps) to `/mnt/data`.
6. **Inspect + repair.** Run `ffprobe`, verify the presence and level of the spoken audio, inspect representative frames from **every** shot (start, middle, end), and review the completed video for flow. Check text bounds, crops, subject consistency, legibility, scene timing, audio sync and factual accuracy. Fix specific failures and rerender; do at most two targeted repair passes before reporting a blocker rather than delivering a flawed “final”.
7. **Deliver.** Link the playable `sandbox:/mnt/data/*.mp4` in chat and state duration and audio status. No auto-posting. No paid generation or externally visible publication without permission. Do not change this repository while generating a video unless asked.

## Channel art direction

**Brand:** bright, memorable and friendly; premium playful 2D/3D editorial motion, not noisy clickbait. Cohesive across episodes but each fact gets its own expressive subject and fresh scenes.

- **Palette:** primary blue `#2386F8`, deep navy `#101C35`, warm white `#FFFDF5`; highlights yellow `#FFE352` and occasional coral `#FF7966`. Use no more than two accents per scene; prioritize contrast and legibility over saturation.
- **Typography:** one geometric sans family (e.g. Manrope/Inter, with a Cyrillic-capable fallback), two weights, kinetic emphasis on key words. Copy is short; headings ideally up to two lines. Do not repeat a huge header in every shot. Avoid rough brush fonts and fake AI-generated lettering.
- **Composition:** one focal subject and one clear text hierarchy per shot. Reserve roughly 8% horizontal margins, 12% at top and 20% at bottom for Shorts UI. Text must fit *within* its allocated safe box; shrink/reflow or move it away from the subject rather than cropping or overlapping. Apply a subtle contrast scrim/plate over busy imagery. Keep diagrams schematic, correct and readable.
- **Motion:** intentional camera parallax, object transitions, animated diagrams and responsive typography. Introduce new visual meaning about every 1–2 seconds but avoid strobing, constant random zooms, excess noise and rapid flashing. Infographics should explain rather than decorate.
- **Consistency:** same design tokens, type scale, motion easing, illustration/render treatment and sound palette in one video; retain the same character/model where a character recurs.

## Files and limits

- Read this file on each new FF session from `tim8es/ff`; load only files relevant to the run. Do **not** read every file in the repository by default.
- `skills/ff-shorts/SKILL.md` is a discovery pointer, not duplicate instructions.
- `examples/wombat.json` is a structural/demo example, **not** final visual quality.
- `scripts/render.py` is a reusable compositor, **not** an image/video generator or TTS service.
- Store per-video script, source list, scene manifest and asset paths together for reproducibility. Do not commit generated footage/assets by default.
- A ChatGPT Project router can request these steps but cannot make unavailable video/TTS tools appear. If a tool, budget or render is blocked, state the exact limitation; **never** present an image sequence as the requested finished video.
