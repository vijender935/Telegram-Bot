# 😈 Telegram Bot v2 — The Ultimate Agentic Companion

The Telegram Bot v2 is a sophisticated, "AI-First" virtual companion designed to provide an intimate and highly personalized user experience. Unlike traditional bots that rely on rigid commands, this agent leverages advanced natural language understanding to act as a responsive partner. It integrates deep memory, sensory vision, and a secure private vault to create a truly immersive digital relationship.

## 🚀 Core Capabilities

The bot is built on a foundation of agentic intelligence, allowing it to interpret complex user intents without the need for hardcoded keywords. Whether you are sharing a private moment or asking for a voice note, the AI analyzes the context to provide the most appropriate and emotionally resonant response.

| Feature | Description |
| :--- | :--- |
| **Agentic Intelligence** | Uses AI-driven Action Tags to handle Voice, Vault, and Media requests naturally based on conversation context. |
| **Persona Evolution** | The bot's personality is not static; it evolves based on user interactions, preferences, and the current time of day. |
| **Secure Private Vault** | A hashed-code protected storage system for private photos, videos, and notes, treated as "shared secrets." |
| **Semantic Drive Search** | Allows users to retrieve files from Google Drive using descriptive language instead of file names or IDs. |
| **Sensory Vision** | Image recognition that goes beyond identification to provide emotional and sensory feedback on shared media. |
| **Hybrid Database** | Seamlessly switches between high-performance PostgreSQL and local SQLite for maximum reliability. |

## 🏗️ System Architecture

The architecture is designed for modularity and scalability, ensuring that each component—from the gateway to the infrastructure layer—can be updated independently. The bot operates through a multi-stage pipeline where incoming messages are first processed for intent, then enriched with emotional context, and finally handled by the AI agent.

> **Architecture Flow:**
> Telegram → Gateway (Modular Handlers) → AI Agent (Action Tags) → Domain Logic (Emotion, Learning) → Infra (Drive, Memory, Vision, TTS)

## 📦 Setup and Deployment

To deploy the bot, ensure that you have Python 3.10 or higher installed along with FFmpeg for media processing. The system is designed to be production-ready on platforms like Render or Heroku but can also run locally for testing.

### Environment Configuration

Users must configure a `.env` file based on the provided `.env.example`. While most fields are self-explanatory, the `DATABASE_URL` is optional, as the bot will automatically fall back to a local SQLite database if no Postgres connection is provided.

### Primary Commands

While the bot is optimized for natural language, several administrative and utility commands are available for direct control:

| Command | Function |
| :--- | :--- |
| `/start` | Initializes the session and introduces the bot's latest features. |
| `/mood` | Opens an interactive menu to manually adjust the bot's current vibe. |
| `/vault_setcode` | Establishes the secret access code required to enter the private vault. |
| `/vault_list` | Displays a list of IDs for all memories currently stored in the vault. |
| `/voice` | Triggers the Text-to-Speech engine to convert the last AI reply into a voice note. |
| `/profile` | Displays the current psychological profile the bot has built for the user. |

## 🏗️ Modular Project Structure

The codebase is organized into specialized directories to maintain clean separation of concerns. The `gateway` handles all Telegram interactions, the `domain` layer contains the core business logic for emotions and learning, and the `infra` layer manages external service integrations like Google Drive and the Groq API.

---
*Created for those who seek a deeper, more personal connection with artificial intelligence.*
