# FF — chat-first short video studio

A minimal, reusable workflow for colorful, narrated Shorts about surprising and useless-but-verified facts. The assistant plans, generates, animates, narrates, checks and delivers the MP4 **inside ChatGPT**.

## ChatGPT Project setup

Create a ChatGPT Project named **FF**, then paste this **router** into its Project instructions:

> Ты — FF, автономная студия коротких видео. Когда я пишу «Создай видео» или указываю тему, загрузи актуальный `AGENTS.md` из репозитория `tim8es/ff` через доступный GitHub-инструмент (для публичного репозитория допускается веб-доступ). Выполни описанный там цикл целиком прямо в этом чате: выбор и проверка факта, сценарий, генерация визуалов, анимация, естественная русская или согласованная английская озвучка, звук, проверка и самостоятельные исправления, экспорт реального MP4. Если тема не указана — выбери её сам. Не заменяй видео картинками и не объявляй успех без проверки результата. Не публикуй и не используй платные сервисы без моего согласия. Об изменениях репозитория спрашивай отдельно.

That is the **only** project-level instruction. No pasted code, local command setup or additional agents are required to describe the workflow.

## Run

Inside the FF project, simply write **«Создай видео»** or **«Создай видео про три сердца осьминога»**.

The authoritative process and visual brand are in [AGENTS.md](AGENTS.md). [Skill pointer](skills/ff-shorts/SKILL.md) supports discovery by coding agents. The [renderer](scripts/render.py) composites imagery and deterministic graphics; [tts.py](scripts/tts.py) creates scene-synchronized neural speech using selectable local or online providers; [voice-cloning setup](docs/voice-cloning.md) supports authorized EN/RU voice references; [qa.py](scripts/qa.py) enforces release checks. Actual generation still requires capable tools and outgoing TTS network access. A GitHub repository or ChatGPT instruction cannot grant those capabilities automatically.

## Release path (fail-closed)

Each episode has a `manifest.json` with `language` (`ru` or `en`), independent `sources` and 5–8 scenes. Each scene records `duration`, `narration`, `onscreen_text` and `visual_intent`, `motion_cue` and `visual_asset` (at least three distinct source assets). Generate diverse text-free images; render exact typography/diagrams as overlays. Review the result and set all seven review keys to `true` only if actually checked.

```bash
python -m pip install -r scripts/requirements.txt
python -m scripts.tts --manifest /path/to/manifest.json --output /path/to/voice.wav
python scripts/render.py /path/to/manifest.json --assets /path/to/assets --audio /path/to/voice.wav --output /path/to/final.mp4
python -m scripts.qa /path/to/manifest.json --video /path/to/final.mp4 --voice /path/to/voice.wav --receipt /path/to/voice.voice.json --review /path/to/review.json --report /path/to/qa.json
```

Required `review.json` booleans: `speech_understandable`, `facts_verified`, `motion_matches_narration`, `no_visual_artifacts`, `text_inside_safe_areas`, `hook_is_immediate`, `pace_and_ending_work`. Any missing or false check blocks release. This is a quality *gate*, not an assertion that automation can judge artistic quality.

The example uses an English voice, so set `language` to `en` and write **all** narration/captions in English. For Russian prefer a verified local provider or Qwen cloning with an authorized reference; use a Russian Edge voice only if the live probe confirms it. On 30 Oct 2026 the hosted smoke test found both Russian Edge voices unavailable but the English one working. Edge TTS is unofficial and online; it needs network access, may change without notice, and must never silently fall back to eSpeak. Equivalent independently evaluated neural voices can be used with a matching provenance receipt. GitHub does not automatically launch video production from a chat message.

## Local fallback and tests

Requires Python 3.11+, Pillow, FFmpeg / FFprobe:

```bash
python -m pip install -r scripts/requirements.txt
python scripts/render.py examples/wombat.json --output /tmp/wombat.mp4
python -m unittest discover -s tests -v
```

To include generated hero imagery use `--assets path/to/images` and scene `image` fields. To include narration use `--audio /path/to/final_mix.wav`. The built-in wombat example intentionally illustrates the basic compositor only and **does not meet final channel quality**.

No autonomous publishing, no paid services without consent, and no changes to repo instruction files during ordinary generation.
