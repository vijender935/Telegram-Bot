# Contributing

## Local setup

Use Python 3.11, install `requirements.txt`, configure `.env`, and make sure FFmpeg is available.

## Before opening a PR

```bash
python -m compileall bot tests
ruff check bot tests
pytest
```

Keep changes focused, preserve existing Telegram command compatibility, add tests for new behavior, and never commit secrets or private media.

## Architecture rule

Prefer new behavior in `core`, `domain`, `application` or `infrastructure` layers. Keep Telegram-specific formatting inside `gateway`.
