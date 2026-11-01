"""Five-shot synthetic art fixture for CPU/video plumbing tests ONLY.

This is *not* an FF release: facts are not verified and imagery is deliberately
abstract. Human/agent content review must precede any production release.
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

PALETTE = {
    "bg": "#101C35", "fg": "#FFFDF5",
    "accent": "#FFE352", "muted": "#D7E6FF",
}


def make_demo(directory):
    directory = Path(directory)
    assets = directory / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    titles = [
        ("TECHNICAL DEMO", "A VIDEO PIPELINE TEST", "Not a verified fact.",
         "Here is a technical preview.", "#2386F8"),
        ("THREE ASSETS", "DIFFERENT IMAGES", "Illustrations are test fixtures.",
         "Three different pictures appear.", "#FF7966"),
        ("CLEAN TYPE", "SEPARATE TEXT", "Text overlays stay editable.",
         "The text is drawn separately.", "#5A6EE5"),
        ("NEURAL VOICE", "SYNCHRONIZED SPEECH", "Audio must match the scenes.",
         "The audio matches each scene.", "#179AA5"),
        ("REVIEW GATE", "NOT A FINAL RELEASE", "A human must approve quality.",
         "Review is required before release.", "#AA6DDA"),
    ]
    scenes = []
    for i, (eyebrow, title, caption, narration, color) in enumerate(titles):
        image_name = f"fixture_{i}.png"
        canvas = Image.new("RGB", (720, 1280), color)
        d = ImageDraw.Draw(canvas)
        # Five distinct original geometric motifs; never pass as final generated art.
        center_x, center_y = 360, 880
        if i == 0:
            d.polygon([(360, 680), (575, 860), (360, 1080), (145, 860)],
                      fill="#FFE352")
            d.ellipse((290, 785, 430, 925), fill="#101C35")
        elif i == 1:
            for n in range(5):
                x = 110 + 105*n
                d.ellipse((x-50, 735+n*30, x+50, 835+n*30),
                          fill=["#FFFDF5", "#FFE352", "#101C35"][n%3])
        elif i == 2:
            for n in range(4):
                x=130+120*n
                d.rounded_rectangle((x-52, 700+n*24, x+52, 1050-n*19),
                                    radius=25, fill="#FFFDF5" if n%2 else "#FFE352")
        elif i == 3:
            for n in range(16):
                x = 90 + 35*n
                height = int(80+135*abs(math.sin(n*.66)))
                d.rounded_rectangle((x, 900-height, x+20, 900+height),
                                    radius=10, fill="#FFE352")
        else:
            d.ellipse((175, 690, 550, 1065), fill="#FFFDF5")
            d.ellipse((260, 775, 465, 980), fill="#101C35")
            d.polygon([(315, 863), (350, 907), (433, 808)],
                      fill="#FFE352")
        canvas.save(assets / image_name)
        scenes.append({
            "type": "image", "duration": 3.4,
            "image": image_name, "visual_asset": image_name,
            "eyebrow": eyebrow, "title": title, "caption": caption,
            "narration": narration, "onscreen_text": f"{title}: {caption}",
            "visual_intent": f"Demonstrate renderer feature {i+1} with unique fixture",
            "motion_cue": "Subtle camera pan on static test image",
        })
    manifest = {
        "width": 720, "height": 1280, "fps": 24, "language": "en",
        "palette": PALETTE,
        "sources": ["https://example.org/placeholder-not-evidence",
                    "https://example.com/placeholder-not-evidence"],
        "tts": {"provider": "piper"},
        "scenes": scenes,
        "demo_only": True,
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    return directory
