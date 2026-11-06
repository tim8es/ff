"""FF PUBLIC Actions must never process the owner's personal voice."""
import unittest
from pathlib import Path


class FFPrivateBoundaryTests(unittest.TestCase):
    def test_public_actions_are_draft_only(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github" / "workflows" / "production.yml").read_text()
        self.assertIn("options: [demo, staged]", workflow)
        self.assertIn("voice-mode piper", workflow)
        self.assertNotIn("FF_VOICE_BUNDLE_KEY", workflow)
        self.assertNotIn("FF_JOB_FERNET_KEY", workflow)
        self.assertNotIn("VOICE_ENGINE_REPO_TOKEN", workflow)
        self.assertNotIn("qwen-tts", workflow)
        self.assertNotIn("mode: owner", workflow)
        self.assertNotIn("encrypted-reference", workflow)
        self.assertNotIn(".private_voice/", workflow)

    def test_historic_qwen_benchmark_cannot_run_private_reference(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github" / "workflows" /
                    "qwen-base-compare.yml").read_text()
        self.assertIn("options: [demo]", workflow)
        self.assertIn("inputs.mode == 'demo'", workflow)
        self.assertNotIn("options: [demo, private]", workflow)

    def test_owner_audio_is_accepted_only_with_checked_external_receipt(self):
        root = Path(__file__).resolve().parents[1]
        production = (root / "scripts" / "production.py").read_text()
        verifier = (root / "scripts" / "external_voice.py").read_text()
        instructions = (root / "AGENTS.md").read_text()
        self.assertIn('voice_mode == "external"', production)
        self.assertIn("accept_owner_voice(", production)
        self.assertIn("Qwen/Qwen3-TTS-12Hz-1.7B-Base", verifier)
        self.assertIn("audio_sha256", verifier)
        self.assertIn("script_sha256", verifier)
        self.assertIn("scene_durations", verifier)
        self.assertIn("universal.yml", instructions)
        self.assertIn("FF_UNIVERSAL_PIPELINE.md", instructions)


if __name__ == "__main__":
    unittest.main()
