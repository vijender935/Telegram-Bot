# Security Policy

## Scope

This bot handles Telegram messages, media metadata, AI prompts, Google Drive access and vault credentials. Treat production secrets and the SQLite database as sensitive.

## Operational checklist

- Configure `ALLOWED_USER_IDS` in production.
- Never commit `.env`, service-account JSON or API keys.
- Mount a persistent disk for SQLite and back it up regularly.
- Rotate provider credentials if exposed.
- Keep the bot on a single worker while using SQLite/in-process rate limits.
- Review vault backups carefully because the vault currently stores Telegram file references; credential protection does not make the referenced Telegram media cryptographically encrypted.

## Vault threat model

v3 improves authentication with PBKDF2-SHA256, temporary lockout and short unlock sessions. This protects the access credential but is **not equivalent to encrypted file storage**. Telegram file IDs and media remain governed by Telegram's storage/access model.

If cryptographic at-rest protection is required, introduce an encrypted object-storage layer before claiming the vault is an encrypted vault.

## Reporting

Do not publish credentials, tokens, private media or database files in issues. Rotate exposed secrets immediately and report the vulnerability privately to the repository owner.
