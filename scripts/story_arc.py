"""Static editorial structure gate for new FF Shorts.

Checks narrative intent, not subjective quality: human visual/audible review
is still required before a video may be released.
"""
from __future__ import annotations

BEATS = ("hook", "evidence", "reveal", "payoff")


def validate_story_arc(manifest):
    if manifest.get("demo_only"):
        return {"validated": False, "reason": "technical fixture"}
    scenes = manifest.get("scenes", [])
    arc = manifest.get("story_arc")
    if not isinstance(arc, dict):
        raise ValueError("Production episode requires story_arc (hook, evidence, reveal, payoff)")
    if not 5 <= len(scenes) <= 8:
        raise ValueError("Shorts story arc requires 5-8 directed scenes")
    for beat in BEATS:
        value = arc.get(beat)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"story_arc.{beat} is required")
    if scenes[0].get("beat") != "hook":
        raise ValueError("First scene must be tagged beat=hook")
    if scenes[-1].get("beat") != "payoff":
        raise ValueError("Final scene must be beat=payoff")
    beats = [scene.get("beat") for scene in scenes]
    if "evidence" not in beats[1:-1] or "reveal" not in beats[1:-1]:
        raise ValueError("Story requires evidence and reveal between hook and payoff")
    lead = scenes[0].get("narration", "").strip().casefold()
    spoken_hook = arc["hook"].strip().casefold()
    if not lead.startswith(spoken_hook):
        raise ValueError("Hook must be audible at the beginning of the first scene")
    ending = scenes[-1].get("narration", "").strip().casefold()
    if arc["payoff"].strip().casefold() not in ending:
        raise ValueError("Payoff must be spoken in the final scene")
    for idx, scene in enumerate(scenes):
        if scene.get("beat") not in BEATS:
            raise ValueError(f"Scene {idx} has unknown beat")
        if not scene.get("visual_intent") or not scene.get("motion_cue"):
            raise ValueError(f"Scene {idx} needs purposeful visual intent and motion cue")
        if not scene.get("evidence"):
            raise ValueError(f"Scene {idx} needs evidence/source attribution")
    return {"validated": True, "beats": beats,
            "note": "Structure only; never an automatic claim of audience retention"}
