# Security Policy

## Scope

This bot handles Telegram messages and media, AI prompts, a local SQLite database, and a custom Cloudflare MCP integration. Treat production secrets, API keys, SQLite data, and downloaded media as sensitive.

## Operational checklist

- Never commit `.env`, provider credentials, webhook secrets, API keys or database files.
- Configure `TELEGRAM_WEBHOOK_SECRET` and `ADMIN_API_KEY` with long random values in production.
- Mount a persistent disk for SQLite and back it up regularly.
- Keep the bot on a single worker while using SQLite and in-process rate limiting.
- Rotate provider credentials immediately if they are exposed.
- Treat API keys as bearer credentials; store client keys securely and revoke them when compromised.
- Keep the custom Cloudflare MCP endpoint and API key restricted to the required resources.

## API security

- REST endpoints use scoped API keys with SHA-256 token hashes stored in SQLite.
- API identity is derived from the authenticated key; callers cannot select an arbitrary Telegram user ID.
- Administrative key-management endpoints require the separate `ADMIN_API_KEY`.
- API requests are rate-limited and AI/tool execution has bounded timeouts.
- Media/base64 MCP payloads are not returned through the text REST API.
- Telegram webhook requests require the configured Telegram secret token.

## Data protection

SQLite contains conversation history, profiles, session summaries, media metadata and API-key metadata. The API-key database stores token hashes, not plaintext client tokens.

The bot may download Telegram media to the configured sandbox for processing. Apply appropriate persistent-disk access controls and retention policies.

## Reporting

Do not publish credentials, tokens, private media or database files in issues. Rotate exposed secrets immediately and report vulnerabilities privately to the repository owner.