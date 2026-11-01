"""Voice profile and performance metadata contracts (no personal voice fixtures)."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class VoiceProfileTests(unittest.TestCase):
    def test_named_voice_profile_and_fail_closed_override(self):
        from scripts.voice_profiles import resolve_profile
        p = resolve_profile("ff_owner", language="ru")
        self.assertEqual(p["provider"], "qwen3_clone")
        self.assertEqual(p["model_size"], "1.7B")
        self.assertIn("en", p["languages"])
        with self.assertRaisesRegex(ValueError, "Unknown voice profile"):
            resolve_profile("unknown")
        with self.assertRaisesRegex(ValueError, "does not match"):
            resolve_profile("ff_owner", model_size="0.6B")
        with self.assertRaisesRegex(ValueError, "does not match"):
            resolve_profile("ff_owner", provider="kokoro")

    def test_profile_cli_uses_private_environment_not_manifest_paths(self):
        from scripts import tts
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            story = folder / "story.txt"
            story.write_text("This is a short example.", encoding="utf8")
            transcript = folder / "transcript.txt"
            transcript.write_text("These are my private voice words.", encoding="utf8")
            voice = folder / "private_recording.wav"
            with patch.dict(os.environ, {"FF_VOICE_REFERENCE": str(voice),
                                         "FF_VOICE_TRANSCRIPT_FILE": str(transcript)}):
                with patch("sys.argv", ["tts", "--profile", "ff_owner",
                                        "--language", "en", "--text-file", str(story),
                                        "--output", str(folder / "out.wav")]):
                    with patch("scripts.tts.generate", return_value={"ok": True}) as generate:
                        with contextlib.redirect_stdout(io.StringIO()):
                            tts.main()
                self.assertEqual(generate.call_args.kwargs["provider"], "qwen3_clone")
                self.assertEqual(generate.call_args.kwargs["model_size"], "1.7B")
                self.assertEqual(str(generate.call_args.kwargs["reference"]), str(voice))
                self.assertEqual(generate.call_args.kwargs["reference_text"],
                                 transcript.read_text(encoding="utf8"))

    def test_manifest_profile(self):
        from scripts import tts
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "episode.json"
            manifest.write_text(json.dumps({
                "language": "ru",
                "tts": {"profile": "ff_owner"},
                "scenes": [{"narration": "Интересный факт.", "duration": 3.5}],
            }), encoding="utf8")
            with patch("sys.argv", ["tts", "--manifest", str(manifest),
                                    "--output", str(root / "voice.wav")]):
                with patch("scripts.tts.generate", return_value={"ok": True}) as generate:
                    with contextlib.redirect_stdout(io.StringIO()):
                        tts.main()
            self.assertEqual(generate.call_args.kwargs["provider"], "qwen3_clone")
            self.assertEqual(generate.call_args.kwargs["model_size"], "1.7B")

    def test_qwen_perf_report_is_nonbiometric(self):
        from scripts import qwen_batch
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            reference = root / "private-authorized.wav"
            reference.write_bytes(b"fake-audio")
            transcript = root / "secret.txt"
            transcript.write_text("Private voice transcript.", encoding="utf8")
            ru, en = root / "ru.txt", root / "en.txt"
            ru.write_text("Привет.", encoding="utf8")
            en.write_text("Hello.", encoding="utf8")
            class FakeCloner:
                init_count = 0
                model_id = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
                timings = {"model_load_including_download_s": 5.0,
                           "voice_conditioning_s": 1.0}
                def __init__(self, *args, **kwargs):
                    self.__class__.init_count += 1
            def fake_generate(text, dest, **kwargs):
                return {"duration": 3.1, "audio_sha256": "a"*64}
            with patch("scripts.qwen_batch.Qwen3VoiceCloner", FakeCloner):
                with patch("scripts.qwen_batch.generate", fake_generate):
                    with contextlib.redirect_stdout(io.StringIO()) as output:
                        report = qwen_batch.run_batch(
                            profile="ff_owner", reference=reference,
                            reference_text_file=transcript, ru=ru, en=en,
                            output_dir=root / "out")
            self.assertEqual(FakeCloner.init_count, 1)
            self.assertIn("ru_synthesis_and_audio_write_s", report["phases"])
            self.assertIn("en_synthesis_and_audio_write_s", report["phases"])
            self.assertIn("peak_process_rss_mib", report["phases"])
            saved = (root / "out" / "tts_performance.json").read_text(encoding="utf8")
            self.assertEqual(report, json.loads(saved))
            self.assertNotIn(str(reference), saved + output.getvalue())
            self.assertNotIn("Private voice transcript.", saved + output.getvalue())
            self.assertEqual(report["profile"], "ff_owner")
            with self.assertRaisesRegex(ValueError, "does not match"):
                qwen_batch.run_batch(profile="ff_owner", model_size="0.6B",
                                     reference=reference, reference_text_file=transcript,
                                     ru=ru, en=en, output_dir=root / "other")


if __name__ == "__main__":
    unittest.main()
