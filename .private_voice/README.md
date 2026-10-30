# Encrypted voice inputs only

This public directory may contain `reference.bundle` created with `python -m scripts.voice_secure pack-reference`. **Never upload a raw recording, transcription, decryption key, speaker embedding or decrypted WAV here.** Store `FF_VOICE_BUNDLE_KEY` exclusively as a GitHub Actions repository secret. Encryption helps protect public source access but does not protect against an authorized Actions job runner.
