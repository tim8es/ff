# FF: chat-first short video workflow

**Trigger:** User requests FF/ff, “Бесполезные факты” channel Shorts, or asks to repeat the prior wombat video workflow. The output contract is a real video file playable in chat, not a static image, prompt, storyboard, or claim of future delivery.

## Run in this chat

1. **Load spec:** Read this file, `skills/ff-shorts/SKILL.md`, and `examples/wombat.json` from the GitHub repository `tim8es/ff`. Respect the latest committed version. The user should not need to open an external editor or run commands.
2. **Fact and sources:** Find a surprising, verified fact (at least two credible independent references, preferably primary/scientific). Flag uncertainty. Do not make biological/medical diagrams falsely precise.
3. **Script:** Write 15–25 seconds, one factual insight, hook within 1.5 seconds, quick explanation and a memorable funny finish. Keep the narration ~35–55 Russian words. Avoid unverifiable jokes presented as facts.
4. **Shot plan:** 5–8 scenes, each with a unique visual purpose; specify seconds, shot type, motion, typography, and audio cue. Alternate hero imagery, closeups, and clean diagrams rather than making every shot a static infographic.
5. **Generate visuals:** Use available image/video tools in-chat for cohesive character/scene assets. Request **text-free** artwork; captions and diagrams should be composited deterministically. Generate true moving footage if the relevant video tool is available; otherwise apply keyframed camera motion and animated vector overlays in rendering. Use only licensed/authorized assets.
6. **Render:** Create a JSON scene timeline compatible with `scripts/render.py` (or a richer video renderer available in the chat). Use FFmpeg and produce an actual MP4 in `/mnt/data` with 9:16 dimensions, H.264/yuv420p. Generate/load speech and music only if available and permissible; never pretend a silent file has narration.
7. **QA:** Inspect with `ffprobe`: video codec, dimensions, duration, audio. Extract representative frames and check spelling, safe text area, motion pacing, and visual consistency. Verify factual citations. If a render fails, fix and rerender. If blocked by missing tools/assets, disclose it rather than substituting images.
8. **Deliver:** Link the actual `sandbox:/mnt/data/<file>.mp4` and briefly mention duration, audio status, and limitations. Do not auto-publish.

## Style contract

Vertical 9:16; clear minimal *kinetic* typography; TGC-inspired editorial/motion graphic energy; one focal object per shot; fluid camera moves and semantic transitions; animated SVG-like infographics; concise text; high contrast; restrained palette (dark navy / white / yellow / cool blue); attention change when a new meaning enters, not constant chaotic cuts. No big brush-type thumbnail headers on every frame. No gratuitous flashing or unreadable speed. Stay recognizably cohesive between different facts.

## Quality gates

Fact provenance and caveats; usable hook; every scene contributes new information/visual surprise; narration synchronized with on-screen meaning; clean safe margins for Shorts UI; no watermarks or unauthorized copyrighted footage; deterministic export with ffprobe evidence; usable playback link. Reject fabricated anatomy, broken captions, repeated AI compositions, and any project that is only an image sequence mislabeled as a finished video.