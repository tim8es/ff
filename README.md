# FF — chat-first short video studio

A minimal, reusable workflow for colorful, narrated Shorts about surprising and useless-but-verified facts. The assistant plans, generates, animates, narrates, checks and delivers the MP4 **inside ChatGPT**.

## ChatGPT Project setup

Create a ChatGPT Project named **FF**, then paste this **router** into its Project instructions:

> Ты — FF, автономная студия коротких видео. Когда я пишу «Создай видео» или указываю тему, загрузи актуальный `AGENTS.md` из репозитория `tim8es/ff` через доступный GitHub-инструмент (для публичного репозитория допускается веб-доступ). Выполни описанный там цикл целиком прямо в этом чате: выбор и проверка факта, сценарий, генерация визуалов, анимация, русская озвучка, звук, проверка и самостоятельные исправления, экспорт реального MP4. Если тема не указана — выбери её сам. Не заменяй видео картинками и не объявляй успех без проверки результата. Не публикуй и не используй платные сервисы без моего согласия. Об изменениях репозитория спрашивай отдельно.

That is the **only** project-level instruction. No pasted code, local command setup or additional agents are required to describe the workflow.

## Run

Inside the FF project, simply write **«Создай видео»** or **«Создай видео про три сердца осьминога»**.

The authoritative process and visual brand are in [AGENTS.md](AGENTS.md). [Skill pointer](skills/ff-shorts/SKILL.md) supports discovery by coding agents. The current [Python renderer](scripts/render.py) composites generated images and animated infographics; it does not generate images, video clips, speech or music itself. Actual video/voice creation depends on the tools available in the active ChatGPT session. The project router is **not** an installed plugin or a guarantee of access to external services.

## Local fallback and tests

Requires Python 3.11+, Pillow, FFmpeg / FFprobe:

```bash
python -m pip install -r scripts/requirements.txt
python scripts/render.py examples/wombat.json --output /tmp/wombat.mp4
python -m unittest discover -s tests -v
```

To include generated hero imagery use `--assets path/to/images` and scene `image` fields. To include narration use `--audio /path/to/final_mix.wav`. The built-in wombat example intentionally illustrates the basic compositor only and **does not meet final channel quality**.

No autonomous publishing, no paid services without consent, and no changes to repo instruction files during ordinary generation.
