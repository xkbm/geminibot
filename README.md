# GeminiBot

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Discord](https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com)
[![Gemini](https://img.shields.io/badge/Gemini-API-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)

[**Español**](README.es.md)

A free AI Discord bot that speaks English and Spanish, powered by Google Gemini. It can see images, read PDFs, listen to audio, fetch web content, and maintain conversation context across channels.

> Deploy for free on **[OrionHost](https://orionhost.xyz)**

---

## Features

- **Multimodal** — accepts images, PDFs, videos, audio, and text files as attachments
- **Web reading** — fetches and summarizes page content from links
- **Conversation memory** — maintains context per channel, persists across restarts
- **Bilingual** — responds in English by default, switches to Spanish if you write in Spanish
- **Auto-retry** — handles rate limits with exponential backoff
- **Per-guild channel config** — use `!setchannel` to set which channel the bot watches

---

## Quick Start

### Prerequisites

- Python 3.10+
- A Discord bot token ([how to create one](https://discord.com/developers/applications))
- A Gemini API key ([get one here](https://aistudio.google.com/apikey))

### Install & Run

```bash
git clone https://github.com/xkbm/geminibot.git
cd geminibot
pip install -r requirements.txt
```

Create a `.env` file:

```env
DISCORD_TOKEN=your_discord_token
GEMINI_API_KEY=your_gemini_api_key
```

Start the bot:

```bash
python bot.py
```

### Set up the channel

In your Discord server, type `!setchannel` in the channel where you want the bot to auto-respond. You can also mention `@GeminiBot` or reply to its messages from any channel.

---

## Commands

| Command | Description |
|---|---|
| `!setchannel` | Auto-respond in this channel |
| `!setchannel disable` | Disable auto-response |
| `!clean` | Clear conversation context |
| `!history` | Show active interaction ID |

---

## Hosting

Recommended free hosting: **[OrionHost](https://orionhost.xyz)**

---

## FAQ

**Bot not responding**
> Make sure you ran `!setchannel` in the channel or mention the bot with `@`.

**Error "Missing DISCORD_TOKEN or GEMINI_API_KEY in .env"**
> Check the `.env` file is correctly written.

**Bot says "rate limited"**
> Wait a few seconds. Gemini limits reset quickly.

---

## License

MIT
