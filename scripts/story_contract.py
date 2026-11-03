"""Structural editorial lint: automation checks beats, not creative judgment.

A valid hook/pivot/payoff plan does not prove that a video is entertaining;
manual/agent audition and frame review are still required to release.
"""

BEATS = {"hook", "setup", "proof", "pivot", "payoff"}


def validate_story(manifest):
    scenes = manifest.get("scenes", [])
    if not 5 <= len(scenes) <= 8:
        raise ValueError("Editorial episodes need 5–8 purposeful shots")
    beats = [scene.get("beat") for scene in scenes]
    if any(beat not in BEATS for beat in beats):
        raise ValueError("Each shot needs a beat: hook/setup/proof/pivot/payoff")
    if beats[0] != "hook" or beats[-1] != "payoff":
        raise ValueError("First shot must hook, final shot must pay off")
    if "pivot" not in beats or "proof" not in beats:
        raise ValueError("Story needs visual evidence and a turning point")
    first = scenes[0]
    if not 0.5 <= first["duration"] <= 4.0:
        raise ValueError("Hook must land within four seconds")
    if len(first.get("narration", "").split()) > 16:
        raise ValueError("Opening sentence too long to be an immediate hook")
    if len(first.get("title", "")) > 52:
        raise ValueError("Hook title too long for shorts")
    if not all(scene.get("visual_intent") and scene.get("motion_cue") for scene in scenes):
        raise ValueError("Every shot needs a precise learning intent and meaningful movement")
    if len({scene.get("visual_asset") for scene in scenes}) < 3:
        raise ValueError("Need at least three independent visual subjects")
    return True