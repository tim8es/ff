"""Regression: adaptive synthesis must update scene lengths AND receipt checksum."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf
from scripts import tts


class TightTTSTests(unittest.TestCase):
    def test_synthesized_scene_lengths_follow_real_audio_not_fixed_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original_durations = [4.5, 4.5, 4.5]
            def fake_speech(text, provider, language, voice, target, **kwargs):
                r=24000
                n=int(r*(1.3+.16*len(text)%3))
                x=np.zeros(n+int(.7*r),dtype=np.float32)
                time=np.arange(n,dtype=np.float32)/r
                x[int(.35*r):int(.35*r)+n]=.15*np.sin(2*np.pi*240*time)
                sf.write(target,x,r)
                return "synthetic-model"
            with patch("scripts.tts.speech",fake_speech):
                receipt = tts.generate(["One.", "Two.", "Three."], root/"voice.wav",
                                       provider="piper", language="en",
                                       durations=original_durations,pacing="tight")
            self.assertEqual(receipt["pacing"],"tight")
            self.assertEqual(len(receipt["scene_durations"]),3)
            self.assertLess(sum(receipt["scene_durations"]),sum(original_durations))
            self.assertEqual(receipt["scene_count"],3)
            self.assertEqual(receipt["model"],"en_US-lessac-medium")
            self.assertTrue((root/"voice.voice.json").is_file())
            report=json.loads((root/"voice.voice.json").read_text())
            self.assertEqual(report["scene_durations"],receipt["scene_durations"])
            self.assertTrue(all(entry["trim_lead_s"]>0 for entry in receipt["pacing_details"]))

    def test_unknown_pacing_fails_before_model_load(self):
        with self.assertRaisesRegex(ValueError,"Unsupported pacing"):
            tts.generate("test","out.wav",provider="piper",pacing="rushed")


if __name__=="__main__":
    unittest.main()
