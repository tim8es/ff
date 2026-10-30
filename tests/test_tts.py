import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import tts


class ProviderTests(unittest.TestCase):
    def test_registry_and_languages(self):
        self.assertEqual(set(tts.BACKENDS), {"silero", "kokoro", "piper", "edge"})
        self.assertEqual(tts.resolve_voice("silero", "en"), "en_0")
        self.assertEqual(tts.resolve_voice("kokoro", "en"), "af_heart")
        with self.assertRaisesRegex(ValueError, "does not support"):
            tts.resolve_voice("kokoro", "ru")
        with self.assertRaisesRegex(ValueError, "Unknown provider"):
            tts.resolve_voice("invented", "en")

    def test_speech_split(self):
        self.assertEqual(tts.split_sentences("First. Second? Third!"),
                         ["First.", "Second?", "Third!"])

    def test_generated_audio_and_receipt(self):
        import numpy as np
        def fake_backend(text, voice, lang):
            sample_rate = 24000
            x = np.arange(24000 * 10, dtype=np.float32) / sample_rate
            return (0.2 * np.sin(2 * np.pi * 440 * x), sample_rate, "test-model")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "test.wav"
            with patch.dict(tts.BACKENDS, {"silero": fake_backend}):
                receipt = tts.generate("This is a test.", output, provider="silero")
            self.assertTrue(output.is_file())
            self.assertGreater(receipt["duration"], 9)
            self.assertEqual(receipt["engine"], "silero")
            self.assertEqual(receipt["status"], "generated_not_auditioned")
            self.assertEqual(receipt["audio_sha256"],
                             hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(receipt,
                             json.loads(output.with_suffix(".voice.json").read_text()))
            self.assertIn("noncommercial", receipt["license_note"])


if __name__ == "__main__":
    unittest.main()
