"""CI guard against plaintext voice and key files in public FF checkout."""
import unittest
from pathlib import Path


class PersonalVoiceLeakGuard(unittest.TestCase):
    def test_no_personal_secret_or_plain_audio_in_public_repo(self):
        root = Path(__file__).resolve().parents[1]
        private = root / ".private_voice"
        if private.exists():
            for path in private.rglob("*"):
                if not path.is_file() or path.name == "README.md":
                    continue
                name = path.name.lower()
                if ("key" in name or "secret" in name or path.suffix.lower() in
                        (".wav", ".m4a", ".flac", ".mp3", ".txt")):
                    self.fail("Unencrypted personal voice/credential found in public FF checkout")
                if path.stat().st_size < 500:
                    self.fail("Suspicious tiny personal voice file in public FF checkout")
        self.assertFalse((root / ".private_voice" / "FF_VOICE_BUNDLE_KEY.txt").exists())


if __name__ == "__main__":
    unittest.main()
