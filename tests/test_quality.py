import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.qa import REVIEW_KEYS, audio_levels, inspect_frames, validate
from scripts.voice import compose_timeline, script_hash, verify_script


class QualityGateTests(unittest.TestCase):
    def make_script(self):
        return {
            "language": "ru",
            "sources": [
                "https://science.nasa.gov/venus/venus-facts/",
                "https://www.esa.int/Science_Exploration/Space_Science/",
            ],
            "scenes": [
                {
                    "duration": 3,
                    "narration": f"Проверяемый текст сцены {i}.",
                    "onscreen_text": f"СЦЕНА {i}",
                    "visual_intent": "Показать наблюдаемый факт, а не украшение.",
                    "motion_cue": "Анимировать измерение, обсуждаемое голосом.",
                    "visual_asset": f"asset_{i}.png",
                } for i in range(5)
            ],
        }

    def test_script_hash_is_sensitive_to_changes(self):
        p = self.make_script()
        original = script_hash(verify_script(p))
        p["scenes"][0]["narration"] = "Другой текст."
        self.assertNotEqual(original, script_hash(verify_script(p)))

    def test_missing_narration_blocks_voice(self):
        p = self.make_script()
        p["scenes"][2]["narration"] = ""
        with self.assertRaisesRegex(ValueError, "narration"):
            verify_script(p)

    def test_review_gate_has_explicit_semantic_checks(self):
        self.assertIn("speech_understandable", REVIEW_KEYS)
        self.assertIn("motion_matches_narration", REVIEW_KEYS)
        self.assertIn("text_inside_safe_areas", REVIEW_KEYS)

    def test_audio_timeline_follows_scene_allocation(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("FFmpeg unavailable")
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            parts = []
            for i in range(2):
                part = base / f"{i}.wav"
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=0.4",
                    "-c:a", "pcm_s16le", str(part)], check=True)
                parts.append(part)
            target = base / "voice.wav"
            dur = compose_timeline(parts, [1.0, 1.0], target)
            self.assertEqual(dur, 2.0)
            self.assertGreater(target.stat().st_size, 5000)
            self.assertGreater(audio_levels(target)["max_volume"], -30)

    def test_incomplete_releases_fail_even_if_they_encode(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("FFmpeg unavailable")
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            manifest = base / "manifest.json"
            manifest.write_text(json.dumps(self.make_script()), encoding="utf8")
            video = base / "mp4.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=navy:s=720x1280:r=24:d=15",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                "-t", "15", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)
            ], check=True)
            outcome = validate(manifest, video, None, None, None)
            self.assertFalse(outcome["passed"])
            self.assertTrue(any("voice" in e.lower() for e in outcome["errors"]))
            self.assertTrue(any("review" in e.lower() for e in outcome["errors"]))
            self.assertTrue(any("Blank/black" in e for e in outcome["errors"]))


if __name__ == "__main__":
    unittest.main()
