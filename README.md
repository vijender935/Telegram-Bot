# 😈 Telegram Bot v2 — The Ultimate Agentic Companion

The Telegram Bot v2 is a sophisticated, "AI-First" virtual companion designed to provide an intimate and highly personalized user experience. Unlike traditional bots that rely on rigid commands, this agent leverages advanced natural language understanding to act as a responsive partner. It integrates deep memory, sensory vision, and a secure private vault to create a truly immersive digital relationship.

## 🚀 Core Capabilities

| Feature | Description |
| :--- | :--- |
| **Agentic Intelligence** | Uses AI-driven Action Tags to handle Voice, Vault, and Media requests naturally based on conversation context. |
| **Persona Evolution** | The bot's personality evolves based on user interactions, preferences, and the current time of day. |
| **Secure Private Vault** | A hashed-code protected storage system for private photos, videos, and notes. |
| **Semantic Drive Search** | Allows users to retrieve files from Google Drive using descriptive language instead of file names or IDs. |
| **Sensory Vision** | Image recognition that goes beyond identification to provide emotional and sensory feedback on shared media. |
| **SQLite Memory** | Local SQLite storage for chat history, profile, mood, sessions, media memory, serial maps, and vault metadata. |

## 🏗️ System Architecture

Telegram → Gateway → AI Agent → Domain Logic → Infra (Drive, SQLite Memory, Vision, TTS)

## 📦 Setup and Deployment

Python 3.10+ and FFmpeg are required for local deployment. Configure `.env` from `.env.example`.

### Database

The bot now uses **SQLite as its sole database backend**. SQLite is built into Python, so no database server or external database driver is required.

Set `MEMORY_DB_PATH` when you want to choose the database location. The default is:

- Render with `/var/data` mounted: `/var/data/bot_memory.db`
- Other environments: `/tmp/bot_memory.db`

**Important for Render:** the filesystem outside a mounted persistent disk is ephemeral. If you want memory to survive deploys/restarts, configure a Render persistent disk mounted at `/var/data` (or set `MEMORY_DB_PATH` to a path on your persistent mount). The repository cannot create or attach a Render persistent disk automatically.

### SQLite backup

Back up the SQLite file regularly. A simple manual backup is:

```bash
cp /var/data/bot_memory.db /var/data/bot_memory_backup_$(date +%Y%m%d).db
```

For local development, replace the path with the value of `MEMORY_DB_PATH`.

### Primary Commands

| Command | Function |
| :--- | :--- |
| `/start` | Initializes the session and introduces the bot's latest features. |
| `/mood` | Opens an interactive menu to manually adjust the bot's current vibe. |
| `/vault_setcode` | Establishes the secret access code required to enter the private vault. |
| `/vault_list` | Displays vault metadata. |
| `/voice` | Converts the last AI reply into a voice note. |
| `/profile` | Displays the current profile stored for the user. |

## 🏗️ Modular Project Structure

The codebase is organized into specialized directories. The `gateway` handles Telegram interactions, the `domain` layer contains core business logic, and the `infra` layer manages external service integrations and persistent SQLite memory.

---
*Created for those who seek a deeper, more personal connection with artificial intelligence.*
