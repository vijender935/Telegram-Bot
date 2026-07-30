# Telegram Sexy Bot + Google Drive

Professional OOP structure.

## Structure

```
bot/
├── main.py
├── config.py
├── services/     # DriveService, SandboxStorage
├── tools/        # LangChain tools
├── handlers/     # text, media, commands
└── agent/        # personality + agent
```

## Render

**Start Command:**
```
python -m bot.main
```

## Env variables

- `TELEGRAM_BOT_TOKEN`
- `GROQ_API_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`  (Map folder ID)
- `GOOGLE_SERVICE_ACCOUNT_JSON`  (full JSON string)

## Usage

```
/drive
/list Picture
/download 2
2 download karo
Map folder list karo
Picture folder dikhao
```
