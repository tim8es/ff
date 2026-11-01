"""No real voice recordings in these encryption/Actions contract tests."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf


@unittest.skipUnless(importlib.util.find_spec("cryptography"), "optional cryptography runtime")
class VoiceBundleTests(unittest.TestCase):
    def test_cryptographic_roundtrip_and_wrong_key_rejected(self):
        from cryptography.fernet import Fernet
        from scripts import voice_secure
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            wav = folder / "authorized_synthetic_voice.wav"
            t = np.arange(24000 * 5, dtype=np.float32) / 24000
            sf.write(wav, 0.1 * np.sin(2 * np.pi * 250 * t), 24000)
            transcript = folder / "transcript.txt"
            transcript.write_text("A synthetic reference, not a real voice.", encoding="utf8")
            key = Fernet.generate_key().decode()
            encrypted = folder / "reference.bundle"
            with patch.dict(os.environ, {"FF_VOICE_BUNDLE_KEY": key}):
                voice_secure.pack(wav, transcript, encrypted)
                raw = encrypted.read_bytes()
                self.assertNotIn(b"A synthetic reference", raw)
                self.assertNotIn(wav.read_bytes()[:32], raw)
                target = folder / "decoded"
                voice_secure._decrypt(encrypted, set(voice_secure.REFERENCE), target)
                self.assertEqual((target / "reference.wav").read_bytes(), wav.read_bytes())
                self.assertEqual((target / "reference.txt").read_text(),
                                 transcript.read_text())
                result_folder = folder / "result"
                result_folder.mkdir()
                sf.write(result_folder / "qwen_ru.wav", np.zeros(24000 * 3), 24000)
                sf.write(result_folder / "qwen_en.wav", np.zeros(24000 * 3), 24000)
                for lang in ("en", "ru"):
                    (result_folder / ("qwen_" + lang + ".voice.json")).write_text(
                        json.dumps({"engine": "qwen3_clone", "lang": lang}), encoding="utf8")
                metrics = {"model": "Qwen3 1.7B", "phases": {"total_s": 12.5}}
                (result_folder / "tts_performance.json").write_text(
                    json.dumps(metrics), encoding="utf8")
                artifact = folder / "result.bundle"
                voice_secure.pack_results(result_folder, artifact)
                output = folder / "output"
                required = {"qwen_ru.wav", "qwen_en.wav",
                            "qwen_ru.voice.json", "qwen_en.voice.json"}
                expected = required | {"tts_performance.json"}
                voice_secure._decrypt(artifact, expected, output, required=required)
                self.assertEqual(sorted(p.name for p in output.iterdir()), sorted(expected))
                self.assertEqual(json.loads((output / "tts_performance.json").read_text()),
                                 metrics)
                self.assertNotIn(b"total_s", artifact.read_bytes())

            with patch.dict(os.environ, {"FF_VOICE_BUNDLE_KEY": Fernet.generate_key().decode()}):
                with self.assertRaisesRegex(ValueError, "Wrong key"):
                    voice_secure._decrypt(encrypted, set(voice_secure.REFERENCE),
                                          folder / "wrong")


if __name__ == "__main__":
    unittest.main()
