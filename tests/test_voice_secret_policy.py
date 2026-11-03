"""Prevent repeat of the Nov 2026 plaintext voice-key exposure."""
import re
import unittest
from pathlib import Path


class TestVoiceSecretsStayPrivate(unittest.TestCase):
    def test_no_voice_secret_or_plain_reference_in_public_checkout(self):
        root = Path(__file__).resolve().parents[1]
        private = root / ".private_voice"
        if private.is_dir():
            for path in private.rglob("*"):
                if not path.is_file() or path.name == "README.md":
                    continue
                name = path.name.lower()
                if ("key" in name or "secret" in name
                        or path.suffix.lower() in (".wav", ".m4a", ".flac", ".mp3", ".txt")):
                    self.fail(f"Unsafe public voice or key file: {path.relative_to(root)}")
                if path.stat().st_size < 500:
                    self.fail("Tiny unencrypted private-voice file in public checkout")
                # Do not print any personal content or secret bytes.
        self.assertFalse((root / ".private_voice" / "FF_VOICE_BUNDLE_KEY.txt").exists())


if __name__ == "__main__":
    unittest.main()
