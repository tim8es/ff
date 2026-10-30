# FF: Qwen3 0.6B and 1.7B on GitHub Actions

The [Qwen Base comparison workflow](../.github/workflows/qwen-base-compare.yml) runs **inside the public FF repository**, with two independent GitHub-hosted Ubuntu CPU jobs for Qwen3 Base 0.6B and 1.7B. Each produces identical RU and EN short narration. No API key, GPU, paid TTS, or third-party publishing service is needed for the public demo.

## Modes

- **demo** (also auto-runs on workflow changes): use Qwen's official **public demo** recording; upload plain WAVs as **public demo artifacts**. Use this to establish whether 1.7B runs on GitHub Actions and whether it improves the output.
- **private** (manual dispatch on main only): decrypt one *encrypted* reference with the repository's Actions secret, generate EN + RU WAV, immediately **encrypt the generated WAVs and receipts**, remove cleartext, and upload **only encrypted artifacts** with one-day retention. Personal recording, voice embedding, and derived personal audio are never uploaded to public artifacts in plaintext.

> A public repo is not private. Only the ciphertext may be committed and uploaded; the encryption key must **never** be checked in, shared in logs, or supplied as a workflow input. Repo administrators, workflow editors or a compromised runner could theoretically access the key or plaintext during execution. This is protection against casual public access, not a guarantee of end-to-end isolation from GitHub infrastructure.

## One-time private configuration (requires repository owner)

1. On your own trusted machine, install FF requirements, FFmpeg and \`cryptography\`.
2. Create the exact transcript matching a 3–30-second **WAV** reference. Use \`scripts/voice_secure.py\` to encrypt the reference **locally**:

   \`\`\`bash
   python - <<'PY'
   from cryptography.fernet import Fernet
   from pathlib import Path
   Path("FF_VOICE_BUNDLE_KEY.txt").write_text(Fernet.generate_key().decode(), encoding="ascii")
   PY
   # Paste the generated key into FF_VOICE_BUNDLE_KEY secret via GitHub Settings (see step 3).
   # On local shell ONLY: use the key as an environment variable for the pack command.
   # bash example:
   export FF_VOICE_BUNDLE_KEY="$(cat FF_VOICE_BUNDLE_KEY.txt)"
   python -m scripts.voice_secure pack-reference \
     --source /private/voice.wav --transcript /private/ref.txt \
     --dest /private/reference.bundle
   unset FF_VOICE_BUNDLE_KEY
   \`\`\`

3. Open the **FF** repository → **Settings → Secrets and variables → Actions → New repository secret**. Add \`FF_VOICE_BUNDLE_KEY\` with the exact contents of \`FF_VOICE_BUNDLE_KEY.txt\`. Do not add that file to any Git repository.
4. Upload **only** \`reference.bundle\` into \`ff/.private_voice/reference.bundle\` on \`main\` via GitHub's "Add file → Upload files" (or authenticated Git CLI). Do not upload \`voice.wav\`, \`ref.txt\` or the key. The encrypted file is safe only for as long as the key remains secret. Delete the key from shared locations.
5. In **Actions → FF - Qwen3 Base 0.6B vs 1.7B (GitHub CPU) → Run workflow**, select \`private\`. Each model uploads an encrypted \`encrypted_result.bundle\` artifact. None contains cleartext.
6. Download each private artifact into a trusted machine and decrypt locally:

   \`\`\`bash
   export FF_VOICE_BUNDLE_KEY="$(cat FF_VOICE_BUNDLE_KEY.txt)"
   python -m scripts.voice_secure unpack-results \
     --source /private/encrypted_result.bundle --dest /private/results_06
   unset FF_VOICE_BUNDLE_KEY
   \`\`\`

   Use a separate output directory for 1.7B. You'll get \`qwen_ru.wav\`, \`qwen_en.wav\` and their receipts for each model.

GitHub Actions **cannot set its own repository secret securely from this chat's GitHub connector**. This one-time step requires the repo owner; never put a key in a public branch, workflow YAML, issue, PR comment, or chat that is publicly accessible. A repo secret is not the same thing as an Actions workflow input.

## Implementation details and limits

Uses existing \`python -m scripts.tts --provider qwen3_clone --model-size 0.6B|1.7B\` twice (EN + RU). Same text, one model per job, one reference transcript. Qwen model is downloaded as needed on the runner; CPU 1.7B can be slow, use the benchmark rather than assuming it is faster or always better. The 60-minute job timeout can stop an unreasonably slow model.

Outputs have QA receipts from the normal FF pipeline. The encrypted bundle helper is \`scripts/voice_secure.py\`, using Fernet authenticated encryption (AES-128-CBC + HMAC-SHA256). A strong random 256-bit Fernet key is generated locally. No unencrypted personal voice artifacts are stored by the workflow.

No current human voice clone should be described as delivered until all four output WAVs are actually downloaded and reviewed.
