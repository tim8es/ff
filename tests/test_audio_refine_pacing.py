import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from scripts.audio_refine import denoise_reference
from scripts.pacing import compose_tight
from scripts.story_contract import validate_story


class TestAudioRefineAndPacing(unittest.TestCase):
    def test_reference_denoising_preserves_signal_without_clipping(self):
        r = 24000
        t = np.arange(r * 8) / r
        rng = np.random.default_rng(17)
        x = (0.12 * np.sin(t * 2 * np.pi * 205) + .015 * rng.standard_normal(len(t))).astype("float32")
        clean, stats = denoise_reference(x, r, reduction=.5)
        self.assertTrue(np.isfinite(clean).all())
        self.assertEqual(stats["over_limit_samples"], 0)
        self.assertLess(np.max(np.abs(clean)), 0.95)
        self.assertGreater(np.std(clean), .015)
        with self.assertRaises(ValueError):
            denoise_reference(x, r, reduction=1.2)

    def test_scene_duration_tracks_speech_and_removes_edge_silence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rate = 24000
            clips = []
            for i, seconds in enumerate([1.3, 2.0, 1.5]):
                y = np.zeros(round(rate * (seconds + 1.6)), dtype="float32")
                n = round(rate * seconds)
                tt = np.arange(n) / rate
                y[round(rate * .55):round(rate * .55)+n] = .2 * np.sin(2 * np.pi * 260 * tt)
                path = root / f"sample{i}.wav"
                sf.write(path, y, rate)
                clips.append(path)
            durations, report = compose_tight(clips, root / "out.wav")
            self.assertEqual(len(durations), 3)
            self.assertLess(sum(durations), 6.0)
            self.assertGreater(sum(durations), 4.7)
            self.assertTrue(all(entry["trim_tail_s"] > .5 for entry in report))
            data, hz = sf.read(root / "out.wav")
            self.assertEqual(hz, 48000)
            self.assertLess(abs(len(data) / hz - sum(durations)), .002)

    def test_script_requires_hook_evidence_twist_and_payoff(self):
        shots = []
        for i, beat in enumerate(["hook", "setup", "proof", "pivot", "payoff"]):
            shots.append({"beat": beat, "duration": 2.0,
                          "title": "Важный факт", "narration": "Один факт.",
                          "visual_asset": f"unique_{i}.jpg",
                          "visual_intent": "Explain this specific change",
                          "motion_cue": "Reveal next piece of evidence"})
        self.assertTrue(validate_story({"scenes": shots}))
        shots[0]["beat"] = "setup"
        with self.assertRaisesRegex(ValueError, "hook"):
            validate_story({"scenes": shots})