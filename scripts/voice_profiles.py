"""Named FF voice profiles. Only policy is stored here, never biometric data.

Voice reference and transcript are injected from trusted private environment.
A profile is not an authorization to publish or expose a personal voice.
"""

VOICE_PROFILES = {
    "ff_owner": {
        "provider": "qwen3_clone",
        "model_size": "1.7B",
        "languages": ("ru", "en"),
    },
}


def resolve_profile(name, *, language=None, provider=None, model_size=None):
    try:
        item = VOICE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown voice profile: {name}") from exc
    if language is not None and language not in item["languages"]:
        raise ValueError(f"Voice profile {name} does not support {language}")
    if provider is not None and provider != item["provider"]:
        raise ValueError("Profile provider does not match explicit provider")
    if model_size is not None and model_size != item["model_size"]:
        raise ValueError("Profile model size does not match explicit model size")
    return item.copy()
