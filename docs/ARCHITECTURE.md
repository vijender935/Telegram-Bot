# Architecture

## Request lifecycle

```text
Telegram update
  -> allowlist / rate limit
  -> per-user serialization
  -> context + memory retrieval
  -> LLM response
  -> validated action tags (compatibility)
  -> tool/action execution
  -> response rendering
  -> profile/session learning
```

## Boundaries

- `gateway/`: Telegram transport and presentation.
- `application/`: orchestration and use-case facades.
- `domain/`: intent, emotion, mood, learning and memory policy.
- `infra/`: external providers and legacy persistence adapters.
- `core/`: cross-cutting errors, security, health and logging.
- `infrastructure/vectorstore/`: persistent semantic retrieval.

## Migration strategy

The project deliberately keeps the existing `bot.gateway` and `bot.infra` modules as compatibility boundaries. New capabilities are introduced through application/core layers first, then handlers can migrate module-by-module. This prevents a full rewrite from breaking the live bot.

## Scaling boundary

SQLite + in-process locks are appropriate for one worker. If the bot becomes multi-worker or needs high write concurrency, move persistence and rate limiting to PostgreSQL/Redis while keeping the application/domain interfaces unchanged.
