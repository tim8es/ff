"""Production handoff is safe, review-required and does not need model weights."""
import base64
import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import episode_package, production, production_fixture, qa
from scripts.voice import script_hash


def bundle_from(root, output):
    entries = [root / "manifest.json"] + list((root / "assets").glob("*.png"))
    with io.BytesIO() as raw:
        with zipfile.ZipFile(raw, "w") as z:
            for f in entries:
                z.write(f, f.relative_to(root).as_posix())
        output.write_bytes(base64.b64encode(raw.getvalue()))


class ProductionTests(unittest.TestCase):
    def test_staging_contains_original_images_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / "source", root / "target"
            production_fixture.make_demo(source)
            bundle = root / "episode.zip.b64"
            bundle_from(source, bundle)
            episode_package.unpack(bundle, target)
            data = episode_package.verify_assets(target)
            self.assertEqual(len(data["scenes"]), 5)
            self.assertEqual(len({s["image"] for s in data["scenes"]}), 5)
            self.assertEqual(data["language"], "en")
            self.assertTrue((target / "assets" / "fixture_4.png").exists())

    def test_reject_traversal_and_missing_artwork(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for bad_path in ("../secret.txt", "assets/../../secret.png",
                             "assets/test.wav", "/tmp/private.txt"):
                bundle = root / "bad.zip.b64"
                with io.BytesIO() as raw:
                    with zipfile.ZipFile(raw, "w") as z:
                        z.writestr("manifest.json", '{"scenes":[]}')
                        z.writestr(bad_path, "data")
                    bundle.write_bytes(base64.b64encode(raw.getvalue()))
                with self.assertRaisesRegex(ValueError, "Unsafe|Unexpected"):
                    episode_package.unpack(bundle, root / "target")
            fixture = production_fixture.make_demo(root / "fixture")
            (fixture / "assets" / "fixture_1.png").unlink()
            with self.assertRaisesRegex(ValueError, "missing"):
                episode_package.verify_assets(fixture)

    def test_technical_gate_never_claims_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = production_fixture.make_demo(tmp)
            data = json.loads((root / "manifest.json").read_text(encoding="utf8"))
            (root / "final.mp4").write_bytes(b"not-a-real-mp4-tested-via-mocks")
            voice = root / "voice.wav"
            voice.write_bytes(b"not-real-audio")
            receipt = {
                "neural": True, "engine": "piper", "language": "en",
                "script_sha256": script_hash(data["scenes"]),
                "audio_sha256": hashlib.sha256(voice.read_bytes()).hexdigest(),
            }
            rec_path = root / "voice.voice.json"
            rec_path.write_text(json.dumps(receipt))
            probe = {"streams": [
                {"codec_type": "video", "codec_name": "h264",
                 "pix_fmt": "yuv420p", "width": 720, "height": 1280,
                 "avg_frame_rate": "24/1"},
                {"codec_type": "audio", "codec_name": "aac"},
            ], "format": {"duration": "17.0"}}
            with patch("scripts.qa.probe", return_value=probe), \
                 patch("scripts.qa.inspect_frames", return_value={
                     "decoded_frames": 408, "blank_frames": 0,
                     "longest_identical_run": 0}), \
                 patch("scripts.qa.audio_levels", return_value={
                     "mean_volume": -18, "max_volume": -1.5}):
                tech = qa.validate(root / "manifest.json", root / "final.mp4",
                                   voice, rec_path, review=None, technical_only=True)
                normal = qa.validate(root / "manifest.json", root / "final.mp4",
                                     voice, rec_path, review=None)
            self.assertTrue(tech["passed"])
            self.assertFalse(tech["release_ready"])
            self.assertTrue(tech["technical_only"])
            self.assertFalse(normal["passed"])
            self.assertIn("Semantic and audible review is required", normal["errors"])

    def test_seal_private_hides_derived_video(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            self.skipTest("cryptography optional in local environment")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = root / "output"
            files.mkdir()
            for name in production.OUTPUT_NAMES:
                (files / name).write_bytes(("PRIVATE_" + name).encode())
            key = Fernet.generate_key().decode()
            artifact = root / "private.bundle"
            with patch.dict(os.environ, {"FF_VOICE_BUNDLE_KEY": key}):
                production.seal_private(files, artifact)
                self.assertNotIn(b"PRIVATE_final.mp4", artifact.read_bytes())
                recovered = root / "recovered"
                production.unseal_private(artifact, recovered)
                for name in production.OUTPUT_NAMES:
                    self.assertEqual((files / name).read_bytes(),
                                     (recovered / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
