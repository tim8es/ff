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

    def test_qwen_model_size_parameter_and_selection(self):
        import numpy as np
        import soundfile as sf
        from scripts.tts_qwen import Qwen3VoiceCloner
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "fixture.wav"
            sf.write(p, np.zeros(24000 * 5), 24000)

            class FakeModel:
                def create_voice_clone_prompt(self, **kwargs):
                    return ["private-prompt"]
                def generate_voice_clone(self, **kwargs):
                    time = np.arange(24000 * 3, dtype=np.float32) / 24000
                    return [0.12 * np.sin(2 * np.pi * 300 * time)], 24000

            for size, expected in (
                ("0.6B", "Qwen/Qwen3-TTS-12Hz-0.6B-Base"),
                ("1.7B", "Qwen/Qwen3-TTS-12Hz-1.7B-Base"),
            ):
                fake = Qwen3VoiceCloner(p, "Synthetic test voice.", model=FakeModel(),
                                        model_size=size)
                self.assertEqual(fake.model_id, expected)
                with patch("scripts.tts_qwen.Qwen3VoiceCloner", return_value=fake) as mk:
                    receipt = tts.generate(
                        "Checking model selection.", Path(directory) / (size + ".wav"),
                        provider="qwen3_clone", reference=p,
                        reference_text="Synthetic test voice.", model_size=size)
                    mk.assert_called_once_with(p, "Synthetic test voice.", model_size=size)
                    self.assertEqual(receipt["model"], expected)
            with self.assertRaisesRegex(ValueError, "Unsupported Qwen3 model size"):
                Qwen3VoiceCloner(p, "Synthetic test voice.", model=FakeModel(),
                                 model_size="unknown")
            with self.assertRaisesRegex(ValueError, "only supported by qwen3_clone"):
                tts.generate("Hello!", Path(directory) / "wrong.wav",
                             provider="kokoro", model_size="1.7B")

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


class ConverterTests(unittest.TestCase):
    def test_converter_requires_authorized_reference(self):
        from scripts.tts_conversion import validate_reference
        with self.assertRaisesRegex(ValueError, "reference"):
            validate_reference(None)
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as folder:
            short = Path(folder) / "short.wav"
            sf.write(short, np.ones(24000, dtype="float32") * .1, 24000)
            with self.assertRaisesRegex(ValueError, "3–30 seconds"):
                validate_reference(short)
            with self.assertRaisesRegex(ValueError, "reference"):
                tts.generate("Hello.", Path(folder) / "no.wav",
                             provider="kokoro", voice_conversion="chatterbox")

    def test_conversion_attaches_to_existing_backends_and_receipts(self):
        import shutil
        import numpy as np
        import soundfile as sf
        class FakeConverter:
            def __init__(self, reference):
                self.reference = reference
            def convert(self, source, output):
                shutil.copyfile(source, output)
                return output
        def fake_tts(text, voice, lang):
            rate = 24000
            t = np.arange(rate * 10, dtype=np.float32) / rate
            return (0.1 * np.sin(2 * np.pi * 400 * t), rate, "fixture")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private_authorized.wav"
            sf.write(path, np.zeros(24000 * 6), 24000)
            for provider, lang in (("kokoro", "en"), ("piper", "ru")):
                output = Path(folder) / (provider + ".wav")
                with patch.dict(tts.BACKENDS, {provider: fake_tts}):
                    with patch("scripts.tts_conversion.ChatterboxVoiceConverter",
                               FakeConverter):
                        info = tts.generate("Test synthesis.", output,
                                            provider=provider, language=lang,
                                            reference=path,
                                            voice_conversion="chatterbox")
                self.assertTrue(output.exists())
                self.assertTrue(info["voice_cloned"])
                self.assertEqual(info["voice_conversion"], "chatterbox")
                self.assertIn("MIT", info["conversion_license_note"])
                self.assertNotIn(str(path), str(info))
                self.assertEqual(info["audio_sha256"],
                                 hashlib.sha256(output.read_bytes()).hexdigest())

    def test_converter_rejects_unsupported_combination(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(ValueError, "do not stack"):
                tts.generate("Hello.", root / "out.wav", provider="qwen3_clone",
                             voice_conversion="chatterbox")
            with self.assertRaisesRegex(ValueError, "Kokoro EN or Piper RU"):
                tts.generate("Hello.", root / "out.wav", provider="edge",
                             voice_conversion="chatterbox")
            with self.assertRaisesRegex(ValueError, "Unknown voice conversion"):
                tts.generate("Hello.", root / "out.wav", provider="kokoro",
                             voice_conversion="nonexistent")


if __name__ == "__main__":
    unittest.main()
