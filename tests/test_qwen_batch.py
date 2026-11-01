"""Bilingual CPU reuse checks. No personal voice or model weights involved."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class QwenBatchTests(unittest.TestCase):
    def test_two_languages_one_cloner_and_no_reference_in_log(self):
        from scripts import qwen_batch
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            ref = folder / "secret_authorized_voice.wav"
            ref.write_bytes(b"fixture")
            transcript = folder / "secret.txt"
            transcript.write_text("Secret reference words.", encoding="utf8")
            ru, en = folder / "ru.txt", folder / "en.txt"
            ru.write_text("Привет, это тест.", encoding="utf8")
            en.write_text("Hello, this is a test.", encoding="utf8")
            class FakeCloner:
                instances = 0
                model_id = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
                def __init__(self, reference, text, *, model_size):
                    self.__class__.instances += 1
                    self.reference = reference
                    self.text = text
                    self.model_size = model_size
            calls = []
            def fake_generate(text, output, **kw):
                calls.append((text, Path(output).name, kw))
                return {"duration": 5.0}
            printed = io.StringIO()
            with patch("scripts.qwen_batch.Qwen3VoiceCloner", FakeCloner):
                with patch("scripts.qwen_batch.generate", fake_generate):
                    with contextlib.redirect_stdout(printed):
                        qwen_batch.run_batch(model_size="1.7B", reference=ref,
                                             reference_text_file=transcript,
                                             ru=ru, en=en, output_dir=folder / "out")
            self.assertEqual(FakeCloner.instances, 1)
            self.assertEqual([x[1] for x in calls], ["qwen_ru.wav", "qwen_en.wav"])
            self.assertEqual([x[2]["language"] for x in calls], ["ru", "en"])
            self.assertIs(calls[0][2]["_cloner"], calls[1][2]["_cloner"])
            self.assertNotIn(str(ref), printed.getvalue())
            self.assertNotIn("Secret reference words", printed.getvalue())

    def test_reused_cloner_rejects_wrong_reference_and_model(self):
        import numpy as np
        import soundfile as sf
        from scripts import tts
        from scripts.tts_qwen import Qwen3VoiceCloner
        class FakeModel:
            def create_voice_clone_prompt(self, **kwargs):
                return ["test-prompt"]
            def generate_voice_clone(self, **kwargs):
                x = np.arange(24000 * 2, dtype=np.float32) / 24000
                return [np.sin(x * 2 * np.pi * 330) * .1], 24000
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ref = root / "ref.wav"
            other = root / "other.wav"
            sf.write(ref, np.zeros(24000 * 5), 24000)
            sf.write(other, np.zeros(24000 * 5), 24000)
            cloner = Qwen3VoiceCloner(ref, "Test private speech.", model=FakeModel(),
                                      model_size="1.7B")
            args = dict(provider="qwen3_clone", language="en", reference=ref,
                        reference_text="Test private speech.", model_size="1.7B",
                        _cloner=cloner)
            result = tts.generate("Good morning.", root / "good.wav", **args)
            self.assertEqual(result["model"], cloner.model_id)
            self.assertEqual(result["language"], "en")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                tts.generate("Wrong.", root / "bad.wav",
                             **{**args, "reference": other})
            with self.assertRaisesRegex(ValueError, "mismatch"):
                tts.generate("Wrong.", root / "bad2.wav",
                             **{**args, "model_size": "0.6B"})
            with self.assertRaisesRegex(ValueError, "mismatch"):
                tts.generate("Wrong.", root / "bad3.wav",
                             **{**args, "reference_text": "Different transcript"})
            with self.assertRaisesRegex(ValueError, "requires"):
                tts.generate("Wrong.", root / "bad4.wav",
                             provider="piper", _cloner=cloner)


if __name__ == "__main__":
    unittest.main()
