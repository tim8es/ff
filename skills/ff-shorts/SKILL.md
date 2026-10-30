---
name: ff-shorts
description: Use when creating a complete short-form FF video or “Бесполезные факты” episode from a ChatGPT chat request, including autonomously selecting a topic and rendering a narrated MP4.
---

# FF Shorts

Read the latest [AGENTS.md](../../AGENTS.md) in `tim8es/ff` and execute that contract.

- The ChatGPT Project router is only the entrypoint.
- `AGENTS.md` is the single source of truth for production, art direction and quality gates.
- Read `examples/wombat.json` or `scripts/render.py` only when needed for composition/rendering.
- Return an actual voiced MP4 in this chat, or a precise blocker. Never substitute stills for video.
