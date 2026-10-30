import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import tts


class ProviderTests(unittest.TestCase):
    def test_registry_and_languages(self):
        self.assertEqual(set(tts.BACKENDS), {"silero", "kokoro", "piper", "edge", "qwen3_clone"})
        self.assertEqual(tts.resolve_voice("silero", "en"), "en_0")
        self.assertEqual(tts.resolve_voice("kokoro", "en"), "af_heart")
        self.assertEqual(tts.resolve_voice("qwen3_clone", "ru"), "reference")
        self.assertEqual(tts.resolve_voice("qwen3_clone", "en"), "reference")
        with self.assertRaisesRegex(ValueError, "does not support"):
            tts.resolve_voice("kokoro", "ru")
        with self.assertRaisesRegex(ValueError, "Unknown provider"):
            tts.resolve_voice("invented", "en")

    def test_qwen_ref_required_without_loading_model(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "reference"):
                tts.generate("Hello.", Path(directory) / "voice.wav",
                             provider="qwen3_clone", language="en")
            with self.assertRaisesRegex(ValueError, "only valid"):
                tts.generate("Hello.", Path(directory) / "voice.wav",
                             provider="kokoro", language="en",
                             reference=Path(directory) / "recording.wav")
            with self.assertRaisesRegex(ValueError, "preset"):
                tts.generate("Hello.", Path(directory) / "voice.wav",
                             provider="qwen3_clone", language="ru", voice="any")

    def test_qwen_mock_clones_both_languages_without_leaking_reference(self):
        import numpy as np
        import soundfile as sf
        from scripts.tts_qwen import Qwen3VoiceCloner

        class FakeModel:
            def __init__(self):
                self.calls = []
            def create_voice_clone_prompt(self, **kwargs):
                self.calls.append(("prompt", kwargs))
                return ["private-prompt"]
            def generate_voice_clone(self, **kwargs):
                self.calls.append(("generate", kwargs))
                time = np.arange(24000 * 10, dtype=np.float32) / 24000
                return [0.15 * np.sin(2 * np.pi * 300 * time)], 24000

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            private_reference = folder / "secret-voice.wav"
            sf.write(private_reference, np.zeros(24000 * 4), 24000)
            fake = FakeModel()
            cloner = Qwen3VoiceCloner(private_reference, "Private words spoken.", model=fake)
            for lang in ("ru", "en"):
                with patch("scripts.tts_qwen.Qwen3VoiceCloner", return_value=cloner):
                    out = folder / (lang + ".wav")
                    receipt = tts.generate("This is the new story.", out,
                                           provider="qwen3_clone", language=lang,
                                           reference=private_reference,
                                           reference_text="Private words spoken.")
                self.assertTrue(out.is_file())
                self.assertTrue(receipt["voice_cloned"])
                self.assertNotIn(str(private_reference), str(receipt))
                self.assertNotIn("Private words spoken.", str(receipt))
                self.assertEqual(receipt["voice"], "reference")
            self.assertEqual(len([x for x in fake.calls if x[0] == "prompt"]), 1)
            self.assertEqual([x[1]["language"] for x in fake.calls if x[0] == "generate"],
                             ["Russian", "English"])

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
