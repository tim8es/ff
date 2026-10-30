# FF — Chat-first Shorts factory

Reusable production process for short videos about **absurd but verified facts**. The assistant handles research, script, visual assets, motion graphics, MP4 render, and QA **inside the chat**; this repository stores the recipe and offline compositor, not the conversation or generated media.

## Use from ChatGPT

Say: **«FF, сделай Shorts про три сердца осьминога»** or **«Сделай ролик через ff на выбранную тобой тему»**.

The assistant should fetch the current [`AGENTS.md`](AGENTS.md), [`skills/ff-shorts/SKILL.md`](skills/ff-shorts/SKILL.md), and this repository's example. Generate the visuals in the chat, render a real MP4 and return a sandbox file link. **Do not respond with images or a storyboard instead of a requested video.**

This is a reusable chat convention, **not an automatically installed ChatGPT tool or background worker**. A fresh chat needs access to this repository and video-capable tools. The assistant may use a different renderer when necessary, but must produce an actual, verifiable playable video or state the blocker.

## Local fallback

Requires Python 3.11+, Pillow, FFmpeg + FFprobe.

```bash
python -m pip install -r scripts/requirements.txt
python scripts/render.py examples/wombat.json --output /tmp/wombat.mp4
python -m unittest discover -s tests -v
```

Optional: `--assets path/to/generated/images --audio path/to/final_mix.wav`. Image-backed scenes require `image` to point to an existing asset relative to `--assets`. Missing assets raise an error. Without audio the fallback output contains a silent track; supply a properly mixed narration/music file for the final release.

## Production files

- [`AGENTS.md`](AGENTS.md) — how an in-chat assistant runs FF.
- [`skills/ff-shorts/SKILL.md`](skills/ff-shorts/SKILL.md) — reusable workflow and quality gates.
- [`examples/wombat.json`](examples/wombat.json) — example script/scene timeline.
- [`scripts/render.py`](scripts/render.py) — deterministic animated typography/infographic compositor to MP4.
- [`tests/test_render.py`](tests/test_render.py) — render and failure-path tests.

**Scope:** draft videos in the chat, no auto-posting, no paid services without user authorization. Generated visuals, tracks, subtitles and source URLs stay with each project as separate assets and are not committed to GitHub by default.