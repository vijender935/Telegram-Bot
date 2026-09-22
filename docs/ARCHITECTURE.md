# Architecture

## Request lifecycle

```text
Telegram webhook
  -> gateway
  -> per-user serialization
  -> context + memory retrieval
  -> LLM + bounded tool loop
  -> response rendering
  -> profile/session learning

External REST client
  -> API-key authentication + scope check
  -> per-key rate limit
  -> application ChatService
  -> context + memory retrieval
  -> LLM + bounded tool loop
  -> text-only response
```

## Boundaries

- `gateway/`: Telegram transport, commands, media handling and presentation.
- `api/`: versioned REST transport, authentication, scopes, rate limiting and HTTP error handling.
- `application/`: shared use-case services such as `ChatService`.
- `domain/`: conversation context, learning policy and memory-facing business logic.
- `infrastructure/`: SQLite persistence, Cloudflare MCP, media processing and external provider adapters.
- `agent/`: LLM prompt construction, response policy and runtime tool assembly.
- `core/`: configuration, errors, health, security, rate limiting and observability.

## Production invariants

- Telegram and REST clients share the same application-level chat service semantics.
- REST identity is scoped to the authenticated API key; callers cannot select another user's Telegram ID.
- Tool execution is bounded by per-tool timeouts and a configurable maximum number of rounds.
- Media/base64 MCP payloads are not returned through the text REST API.
- SQLite connections use WAL + busy timeouts for the single-worker deployment model.
- `/health` is a liveness endpoint; `/ready` is the deployment readiness endpoint and returns HTTP 503 while required checks are degraded.

## Scaling boundary

SQLite + in-process locks are appropriate for one worker. If the bot becomes multi-worker or needs high write concurrency, move persistence and rate limiting to PostgreSQL/Redis while keeping the application/domain interfaces unchanged.