# 😈 Telegram Bot v3

> AI-first personal companion for Telegram — memory, adaptive persona, vision, voice, a custom Cloudflare MCP image library and a protected private vault.

## Cloudflare MCP migration

The bot now uses the user's own custom cloudflare-mcp server as the remote image/data layer.

- Layered memory facade with persistent SQLite storage and semantic indexing
- Groq tool-calling agent with dynamically discovered MCP tools
- Custom Cloudflare MCP only — no official Cloudflare MCP and no third-party RAG MCP
- R2-backed image storage through ai-images-pilot
- D1 catalog + Vectorize semantic image search
- Native MCP image content delivered directly to Telegram
- PBKDF2 vault security, per-user serialization and rate limiting
- Health endpoint, structured logs, tests and Docker support

## Architecture

```text
Telegram
   │
   ▼
Gateway / UI ── Auth ── Rate Limit ── Error Boundary
   │
   ▼
Groq Agent
   │
   ├── Memory tools
   │
   └── YOUR custom Cloudflare MCP
          │
          ▼
     ai-images-pilot
       ├── R2: ai-images
       ├── D1: ai-images-db
       └── Vectorize: ai-images-index
```

The MCP server exposes ai-images-pilot through a Cloudflare Service Binding. The bot discovers MCP tool schemas at startup instead of hard-coding a separate image-search API client.

## Custom Cloudflare MCP tools

The current MCP server exposes:
- health
- list_images
- search_images
- process_image
- get_image
- list_r2_objects

For image delivery, the agent can call search_images and then get_image. The MCP returns actual image bytes as MCP image content; the Telegram gateway forwards those bytes without Google Drive or a public image URL.

## Quick start

Python 3.11 and FFmpeg are recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

### Environment

Set Telegram/Groq credentials plus the custom Cloudflare MCP endpoint:

```text
CLOUDFLARE_MCP_ENABLED=true
CLOUDFLARE_MCP_URL=https://cloudflare-mcp.vijender935.workers.dev/mcp
CLOUDFLARE_MCP_API_KEY=
CLOUDFLARE_MCP_TIMEOUT_SECONDS=30
CLOUDFLARE_MCP_RETRIES=3
```

No Google Drive credentials are required by the bot.

## Telegram UX

Image/data operations are handled through normal language. Examples:
- Summer street style wali image dikhao
- Latest ready images dikhao
- R2 mein kya pada hai?
- Next pending image process karo

The legacy Google Drive command surface is no longer registered.

## Migration status

1. Google Drive runtime dependency — removed
2. Modal multimodal RAG MCP dependency — removed
3. Custom Cloudflare MCP — integrated
4. Dynamic MCP tool discovery — implemented
5. Natural-language image retrieval — implemented
6. Native MCP image to Telegram delivery — implemented
7. Local memory/vault/persona — retained

## Development

```bash
ruff check bot tests
pytest
python -m compileall bot tests
```

## Docker

```bash
docker compose up --build
```

See repository security documentation for operational guidance.