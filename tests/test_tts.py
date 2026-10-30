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


class CloneContractTests(unittest.TestCase):
    def test_qwen_languages_and_missing_reference(self):
        self.assertEqual(tts.resolve_voice("qwen_clone", "ru"), "reference")
        self.assertEqual(tts.resolve_voice("qwen_clone", "en"), "reference")
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "clone.wav"
            with self.assertRaisesRegex(ValueError, "reference-audio"):
                tts.generate("Hello.", output, provider="qwen_clone",
                             language="en", reference_text="This was said.")
            self.assertFalse(output.exists())

    def test_qwen_transcript_is_mandatory(self):
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / "reference.wav"
            sf.write(reference, np.sin(np.arange(24000 * 5) / 30), 24000)
            with self.assertRaisesRegex(ValueError, "exact reference transcript"):
                tts.generate("Привет!", Path(folder) / "output.wav",
                             provider="qwen_clone", language="ru",
                             reference_audio=reference)
            self.assertFalse((Path(folder) / "output.wav").exists())

    def test_qwen_clone_receipt_with_mock_backend(self):
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reference = root / "synthetic_fixture.wav"
            sf.write(reference, np.sin(np.arange(24000 * 5) / 50), 24000)
            output = root / "output.wav"
            def mocked_clone(text, lang, reference_audio, reference_text):
                self.assertEqual(lang, "ru")
                self.assertEqual(reference_text, "Sample reference.")
                return (np.sin(np.arange(24000 * 10) / 50).astype("float32"),
                        24000, "Qwen/mock")
            with patch("scripts.voice_clone.qwen_clone", mocked_clone):
                info = tts.generate("Привет, это проверка.", output,
                                    provider="qwen_clone", language="ru",
                                    reference_audio=reference,
                                    reference_text="Sample reference.")
            self.assertEqual(info["engine"], "qwen_clone")
            self.assertTrue(info["cloned_from_reference"])
            self.assertTrue(output.exists())
            self.assertNotIn(str(reference), json.dumps(info))
            self.assertNotIn("Sample reference.", json.dumps(info))

    def test_conversion_after_kokoro_without_fake_success(self):
        import shutil
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reference = root / "ref.wav"
            sf.write(reference, np.sin(np.arange(24000 * 6) / 55), 24000)
            output = root / "converted.wav"
            def fake_kokoro(text, voice, lang):
                return (np.sin(np.arange(24000 * 10) / 50).astype("float32"),
                        24000, "Kokoro/mock")
            def fake_convert(source, ref, target):
                self.assertEqual(ref, reference)
                shutil.copyfile(source, target)
                return target
            with patch.dict(tts.BACKENDS, {"kokoro": fake_kokoro}):
                with patch("scripts.voice_clone.chatterbox_convert", fake_convert):
                    receipt = tts.generate(
                        "We are testing this voice.", output,
                        provider="kokoro", language="en",
                        reference_audio=reference, voice_conversion="chatterbox")
            self.assertEqual(receipt["engine"], "kokoro")
            self.assertEqual(receipt["voice_conversion"], "chatterbox")
            self.assertGreater(receipt["duration"], 9)

    def test_short_reference_rejected_before_download(self):
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reference = root / "short.wav"
            sf.write(reference, np.ones(24000, dtype="float32") * .1, 24000)
            with self.assertRaisesRegex(ValueError, "3–30 seconds"):
                tts.generate("Hello.", root / "never.wav",
                             provider="kokoro", language="en",
                             voice_conversion="chatterbox",
                             reference_audio=reference)

    def test_unknown_converter_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "Unsupported voice conversion"):
                tts.generate("Hello.", Path(folder) / "never.wav",
                             provider="kokoro", voice_conversion="unknown")


if __name__ == "__main__":
    unittest.main()
