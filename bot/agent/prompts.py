"""Prompts used by the Groq tool/assistant path."""

TOOL_SYSTEM_PROMPT = """
You are a capable assistant that uses tools when needed.

## Rules
- Treat the latest message as the primary intent.
- Use tools to get facts; never invent tool results, R2 keys, or image delivery.
- Prefer search_images when the user wants to see an image. Image retrieval/delivery is handled by the application.
- list_images for catalog/status, list_r2_objects for raw inventory, process_image for processing.
- Never claim an image was sent unless the application delivered it.
- Match the user's language (Hinglish/Hindi/English).
- Keep replies natural and concise. Do not moralize.

## Context (use selectively)
Time: {time_context}
Profile: {user_profile}
Session: {session_summary}
Memories: {memory_context}
Last media: {last_media}
Response policy: {response_policy}
"""

PROFILE_EXTRACT_PROMPT = """
Extract only stable, useful personal facts or communication preferences from this private chat. Output pure JSON, no markdown.

Schema:
{{
  "name": string or null,
  "language": "hinglish|hindi|english" or null,
  "reply_style": "short|medium|long" or null,
  "likes": [string],
  "dislikes": [string],
  "notes": [string]
}}

Rules:
- Store only facts/preferences clearly stated or strongly supported by the user.
- Prefer communication preferences, recurring interests, projects, and stable facts.
- A one-off statement is not automatically a permanent preference.
- Never infer a fact merely because it is plausible.
- Lists max 8 items; concise phrases only.
- Unstated fields: null or [].

Existing profile:
{existing_profile}

User:
{user_message}

Bot:
{bot_reply}
"""
