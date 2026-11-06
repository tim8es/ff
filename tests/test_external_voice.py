"""FF cannot accept an unverified or unrelated voice as the owner's voice."""
import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from scripts import external_voice, production, production_fixture
from scripts.voice import script_hash


class ExternalVoiceTests(unittest.TestCase):
    def make_fixture(self, root):
        root = Path(root)
        fixture = production_fixture.make_demo(root / "episode")
        manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf8"))
        manifest["tts"] = {"profile": "ff_owner"}
        # Produce a synthetic 16-second fixture: no real personal voice.
        narration = [s["narration"] for s in manifest["scenes"]]
        assert len(narration) == 5
        manifest["language"] = "ru"
        for scene in manifest["scenes"]:
            scene["narration"] = "Это пример синтетической речи."
        (fixture / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf8")
        voice = root / "private.wav"
        with wave.open(str(voice), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x00\x00" * (16000 * 16))
        receipt = {
            "engine": "qwen3_clone",
            "model": external_voice.OWNER_MODEL,
            "neural": True, "voice_cloned": True,
            "profile": "ff_owner", "language": "ru",
            "scene_count": 5, "scene_durations": [3.2] * 5,
            "script_sha256": script_hash(manifest["scenes"]),
            "audio_sha256": hashlib.sha256(voice.read_bytes()).hexdigest(),
        }
        meta = root / "private.json"
        meta.write_text(json.dumps(receipt), encoding="utf8")
        return fixture, voice, meta, manifest, receipt

    def test_accepts_only_matching_private_voice_and_updates_timeline(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture, voice, meta, manifest, receipt = self.make_fixture(temp)
            output = Path(temp) / "output"
            result = []
            def mocked_render(data, _assets, path, *, audio):
                result.extend(scene["duration"] for scene in data["scenes"])
                Path(path).write_bytes(b"synthetic")
            with patch("scripts.production.render_video", side_effect=mocked_render):
                with patch("scripts.production.validate", return_value={
                    "passed": True, "release_ready": False,
                    "duration": 16, "errors": [],
                }):
                    # The fixture itself is used as a staged data package.
                    from scripts.episode_package import pack
                    package = Path(temp) / "episode.zip.b64"
                    pack(fixture, package)
                    result_handoff = production.build(
                        workspace=output, bundle=package,
                        voice_mode="external",
                        external_voice=voice, external_receipt=meta)
            self.assertEqual(result, [3.2] * 5)
            self.assertEqual(result_handoff["provider"], "qwen3_clone")
            self.assertEqual(result_handoff["voice_mode"], "external")
            self.assertFalse(result_handoff["release_ready"])
            self.assertEqual((output / "voice.wav").read_bytes(), voice.read_bytes())
            self.assertEqual(json.loads((output / "voice.voice.json").read_text()),
                             receipt)

    def test_rejects_wrong_voice_model_script_hash_or_scene_duration(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture, voice, meta, manifest, receipt = self.make_fixture(temp)
            for field, wrong in [
                ("model", "Qwen/Qwen3-TTS-12Hz-0.6B-Base"),
                ("engine", "piper"),
                ("profile", "another_user"),
                ("audio_sha256", "a" * 64),
                ("script_sha256", "0" * 64),
                ("scene_count", 6),
                ("scene_durations", [4] * 5),
                ("language", "en"),
            ]:
                with self.subTest(field=field):
                    bad = dict(receipt, **{field: wrong})
                    meta.write_text(json.dumps(bad))
                    with self.assertRaises(ValueError):
                        external_voice.accept_owner_voice(
                            manifest, voice, meta, Path(temp) / "out")
            meta.write_text(json.dumps(receipt))
            manifest["tts"] = {"provider": "piper"}
            with self.assertRaises(ValueError):
                external_voice.accept_owner_voice(
                    manifest, voice, meta, Path(temp) / "out")

    def test_rejects_fake_wav_and_suspicious_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture, voice, meta, manifest, receipt = self.make_fixture(temp)
            voice.write_bytes(b"not-a-real-wav")
            receipt["audio_sha256"] = hashlib.sha256(voice.read_bytes()).hexdigest()
            meta.write_text(json.dumps(receipt))
            with self.assertRaises((ValueError, wave.Error, EOFError)):
                external_voice.accept_owner_voice(
                    manifest, voice, meta, Path(temp) / "out")


if __name__ == "__main__":
    unittest.main()
