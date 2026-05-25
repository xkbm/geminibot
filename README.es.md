# GeminiBot

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/Licencia-MIT-green?style=for-the-badge)](LICENSE)
[![Discord](https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com)
[![Gemini](https://img.shields.io/badge/Gemini-API-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)

[**English**](README.md)

Tu puerta de entrada a Google Gemini en Discord — un asistente bilingüe gratuito que ve imágenes, lee PDFs, escucha audios, obtiene contenido web y recuerda tus conversaciones a través de los canales.

> Despliega gratis en **[OrionHost](https://orionhost.xyz)**

---

## Características

- **Multimodal** — acepta imágenes, PDFs, videos, audios y archivos de texto como adjuntos
- **Lectura web** — obtiene y resume el contenido de enlaces
- **Memoria conversacional** — mantiene contexto por canal, persiste entre reinicios
- **Bilingüe** — responde en inglés por defecto, cambia a español si le escribes en español
- **Reintentos automáticos** — maneja límites de tasa con backoff progresivo
- **Configuración por servidor** — usa `!setchannel` para elegir el canal

---

## Inicio rápido

### Requisitos

- Python 3.10+
- Un token de bot de Discord ([cómo crear uno](https://discord.com/developers/applications))
- Una API key de Gemini ([consíguela aquí](https://aistudio.google.com/apikey))

### Instalar y ejecutar

```bash
git clone https://github.com/xkbm/geminibot.git
cd geminibot
pip install -r requirements.txt
```

Crea un archivo `.env`:

```env
DISCORD_TOKEN=tu_token_de_discord
GEMINI_API_KEY=tu_api_key_de_gemini
```

Inicia el bot:

```bash
python bot.py
```

### Configurar el canal

En tu servidor de Discord, escribe `!setchannel` en el canal donde quieras que el bot responda automáticamente. También puedes mencionar `@GeminiBot` o responder a sus mensajes desde cualquier canal.

---

## Comandos

| Comando | Descripción |
|---|---|
| `!setchannel` | Responde automáticamente en este canal |
| `!setchannel disable` | Desactiva la respuesta automática |
| `!clean` | Limpia el contexto de la conversación |
| `!history` | Muestra el ID de interacción activo |

---

## Hosting

Hosting gratuito recomendado: **[OrionHost](https://orionhost.xyz)**

---

## Preguntas frecuentes

**El bot no responde**
> Asegúrate de haber ejecutado `!setchannel` en el canal o menciona al bot con `@`.

**Error "Missing DISCORD_TOKEN or GEMINI_API_KEY in .env"**
> Revisa que el archivo `.env` esté bien escrito.

**El bot dice "rate limited"**
> Espera unos segundos. Los límites de Gemini se renuevan rápido.

---

## Licencia

MIT
