# 😈 Telegram Bot v3

> **AI-first personal companion for Telegram** — memory, adaptive persona, vision, voice, Google Drive and a protected private vault.

## ✨ What changed in v3

This release restructures the project around production concerns without throwing away the existing Telegram features:

- 🧠 Layered memory facade with persistent SQLite storage and semantic indexing
- 🤖 Structured tool/action registry with validated legacy Action-Tag compatibility
- 🔎 Semantic Drive ranking with an optional `sentence-transformers` embedding backend
- 🔐 PBKDF2 vault credential migration, failed-attempt lockout and short unlock sessions
- 🛡️ Per-user request serialization and configurable rate limiting
- ⚙️ Central typed configuration validation
- ❤️ Health/readiness endpoint and production Waitress server
- 🧪 Pytest + Ruff CI gates
- 💾 Verified SQLite backups with retention
- 🐳 Production Docker image with FFmpeg and non-root runtime
- 🎨 Button-first Telegram home/settings UI
- 📚 Architecture, security, deployment and contribution documentation

## 🧩 Feature map

| Area | Capability |
|---|---|
| Chat | Groq-powered contextual conversation |
| Memory | History, profile, sessions, emotion, media and semantic index |
| Persona | Mood, emotion, profile learning and evolution |
| Vision | Image description and media reactions |
| Voice | TTS plus audio/video transcription |
| Drive | List, search, upload, download and semantic ranking |
| Vault | Protected private media metadata with lockout/session controls |
| Media | Photo, document, audio, video and video-note workflows |
| Operations | Health endpoint, structured logs, graceful error handling |

## 🏗️ Architecture

```text
Telegram
   │
   ▼
Gateway / UI ── Auth ── Rate Limit ── Error Boundary
   │
   ▼
Application Services
   │
   ├── Chat / Orchestration
   ├── Memory
   ├── Drive
   ├── Vault
   └── Media / Voice
   │
   ▼
Domain
   │
   ├── Intent
   ├── Persona / Mood
   ├── Emotion
   └── Session / Learning
   │
   ▼
Infrastructure
   ├── SQLite + semantic index
   ├── Groq
   ├── Google Drive
   ├── FFmpeg
   └── TTS / Vision / Transcription
```

The `bot/` tree remains the compatibility surface for existing handlers while `bot/application`, `bot/core`, `bot/domain/memory` and `bot/infrastructure` provide the new separation-of-concerns layer.

## 🚀 Quick start

Python 3.11 and FFmpeg are recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

### Environment

Copy `.env.example` and provide the required Telegram and Groq credentials. Google Drive is optional.

For Render, mount persistent storage at `/var/data` and keep `MEMORY_DB_PATH=/var/data/bot_memory.db` if you want memory to survive restarts/deploys.

### Health

```text
GET /
GET /health
```

`/health` reports configuration, database-path and FFmpeg readiness.

## 🎛️ Telegram UX

`/start` opens a compact home panel. `/settings` provides memory/profile/mood/privacy shortcuts.

Core commands include:

`/start` · `/settings` · `/mood` · `/profile` · `/clear` · `/voice` · `/drive` · `/search` · `/download` · `/upload` · `/vault_setcode` · `/vault_list` · `/vault_open`

## 🔐 Security notes

- Only allowlisted Telegram IDs are accepted when `ALLOWED_USER_IDS` is configured.
- Vault codes are migrated to PBKDF2-SHA256 with per-code salts.
- Repeated vault failures trigger temporary lockout.
- Sensitive vault command messages are deleted when Telegram permissions allow it.
- User-facing errors avoid exposing provider exceptions.
- Logs are designed to avoid credentials and secrets.

See [SECURITY.md](SECURITY.md) for the threat model and operational checklist.

## 💾 Backups

```bash
MEMORY_DB_PATH=/var/data/bot_memory.db ./scripts/backup_sqlite.sh
```

The script uses SQLite's online backup API, runs an integrity check and removes backups older than the configured retention window.

## 🧪 Development

```bash
ruff check bot tests
pytest
python -m compileall bot tests
```

## 🐳 Docker

```bash
docker compose up --build
```

The image installs FFmpeg, runs as a non-root user and persists `/var/data` through the compose volume.

## 🗺️ Roadmap status

1. Production stability — **implemented**
2. Configuration/error system — **implemented**
3. Testing/CI — **implemented**
4. Memory architecture — **implemented as migration facade**
5. Tool registry — **implemented as structured execution layer**
6. Agent orchestration — **migration seam implemented; legacy tags retained for compatibility**
7. Vault security — **implemented**
8. Semantic Drive — **implemented with optional embeddings + fallback**
9. Persona engine — **existing engine retained and isolated behind domain layer**
10. Telegram UI — **implemented**
11. Repository docs — **implemented**
12. Docker/deployment — **implemented**
13. Observability — **health + structured/redacted logging implemented**
14. Backup/disaster recovery — **verified backup + retention implemented**

## 📄 License

See repository license information.
