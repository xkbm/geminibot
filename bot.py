import os
import sys
import time
import re
import json
import asyncio
import logging
import aiohttp
import base64
import urllib.request
import discord
from discord.ext import commands
from dotenv import load_dotenv
from google import genai

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("bot")

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.1-flash-lite"
HISTORY_FILE = "history.json"
CHANNEL_CONFIG_FILE = "channels.json"

if not DISCORD_TOKEN or not GEMINI_API_KEY:
    log.error("Missing DISCORD_TOKEN or GEMINI_API_KEY in .env")
    sys.exit(1)

client_genai = genai.Client(api_key=GEMINI_API_KEY)
channel_interactions: dict[int, str] = {}
guild_channels: dict[int, int] = {}
cooldown_until: float = 0.0
_http_session: aiohttp.ClientSession | None = None


async def _save_history():
    data = {str(k): v for k, v in channel_interactions.items()}
    await asyncio.to_thread(_write_history, data)

def _write_history(data: dict):
    try:
        tmp = HISTORY_FILE + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, HISTORY_FILE)
        log.info("History saved (%d channels)", len(data))
    except Exception as e:
        log.error("Error saving history: %s", e)


def _load_history():
    if not os.path.exists(HISTORY_FILE):
        return
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k, v in data.items():
            channel_interactions[int(k)] = v
        log.info("History loaded (%d channels)", len(channel_interactions))
    except (json.JSONDecodeError, EOFError):
        log.warning("History corrupted, ignoring. File: %s", HISTORY_FILE)
    except Exception as e:
        log.error("Error loading history: %s", e)


async def _save_channels():
    data = {str(k): v for k, v in guild_channels.items()}
    await asyncio.to_thread(_write_json, CHANNEL_CONFIG_FILE, data)

def _load_channels():
    if not os.path.exists(CHANNEL_CONFIG_FILE):
        return
    try:
        with open(CHANNEL_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k, v in data.items():
            guild_channels[int(k)] = v
        log.info("Channels loaded (%d guilds)", len(guild_channels))
    except (json.JSONDecodeError, EOFError) as e:
        log.warning("Channels file corrupted: %s", e)
    except Exception as e:
        log.error("Error loading channels: %s", e)

def _write_json(name: str, data: dict):
    try:
        tmp = name + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, name)
    except Exception as e:
        log.error("Error writing %s: %s", name, e)

def _extraer_urls(texto: str) -> list:
    url_pattern = r'https?://[^\s]+'
    return re.findall(url_pattern, texto)


async def _get_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
    return _http_session

async def _fetch_url_content(url: str) -> str | None:
    try:
        session = await _get_session()
        async with session.get(url) as response:
            if response.status == 200:
                length = response.content_length
                if length and length > 2 * 1024 * 1024:
                    log.warning("URL too large (%d bytes), skipping %s", length, url)
                    return None
                content_type = response.headers.get('content-type', '')
                if 'text/html' in content_type:
                    text = await response.text()
                    clean = re.sub(r'<[^>]+>', '', text[:3000])
                    return f"Content from {url}:\n{clean.strip()}"
                elif 'text/plain' in content_type:
                    return await response.text()
    except Exception as e:
        log.warning("Could not fetch content from %s: %s", url, e)
    return None


# ── Interacciones con Gemini ─────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    _load_history()
    _load_channels()
    log.info("Connected as %s — Model: %s", bot.user, MODEL_NAME)
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name=MODEL_NAME)
    )


@bot.event
async def on_error(event, *args, **kwargs):
    log.error("Unhandled exception in %s: %s", event, sys.exc_info()[1])


@bot.event
async def on_disconnect():
    log.warning("Bot disconnected")


async def _call_with_retry(
    input_content,
    system_instruction: str,
    channel,
    last_id: str | None = None,
    max_retries: int = 3,
):
    base_wait = 10.0
    kwargs = {
        "model": MODEL_NAME,
        "input": input_content,
        "system_instruction": system_instruction,
        "generation_config": {"temperature": 0.8, "max_output_tokens": 2048},
    }
    if last_id:
        kwargs["previous_interaction_id"] = last_id

    for attempt in range(max_retries):
        try:
            return await asyncio.to_thread(
                client_genai.interactions.create, **kwargs
            )
        except Exception as e:
            err = str(e)
            is_rate_limit = any(
                tag in err for tag in ("429", "503", "RESOURCE_EXHAUSTED")
            )
            if not is_rate_limit:
                raise
            if attempt == max_retries - 1:
                raise
            match = re.search(r'retry\s+in\s+([\d.]+)s', err, re.IGNORECASE)
            wait = float(match.group(1)) if match else base_wait
            log.warning("Gemini API rate limited (attempt %d/%d): %s", attempt + 1, max_retries, e)
            await channel.send(
                f":warning: Gemini API rate limited. Retrying in "
                f"{int(wait)}s (attempt {attempt+1}/{max_retries})..."
            )
            await asyncio.sleep(wait)
            base_wait *= 1.5


# ── Discord utilities ────────────────────────────────────────────

async def _send_response(message: discord.Message, text: str):
    for i in range(0, len(text), 2000):
        fragment = text[i:i + 2000]
        try:
            if i == 0:
                await message.reply(fragment)
            else:
                await message.channel.send(fragment)
        except discord.HTTPException:
            await message.channel.send(fragment)


async def _is_reply_to_bot(message: discord.Message) -> bool:
    if not message.reference or not message.reference.message_id:
        return False
    ref = message.reference.resolved
    if ref is not None:
        return ref.author == bot.user
    try:
        ref = await message.channel.fetch_message(message.reference.message_id)
        return ref.author == bot.user
    except Exception:
        return False


# ── Construcción de input multimodal ──────────────────────────────

MAX_FILE_SIZE = 10 * 1024 * 1024


def _download_b64_sync(url: str) -> tuple[str | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            ct = resp.headers.get('content-type', 'application/octet-stream')
            length = resp.headers.get('Content-Length')
            if length and int(length) > MAX_FILE_SIZE:
                log.warning("File too large (%s), skipping %s", length, url)
                return None, None
            data = resp.read()
            if len(data) > MAX_FILE_SIZE:
                log.warning("File too large (%d bytes), skipping", len(data))
                return None, None
            return base64.b64encode(data).decode("utf-8"), ct
    except Exception as e:
        log.warning("Could not download file from %s: %s", url, e)
        return None, None


async def _download_file_b64(url: str) -> tuple[str | None, str | None]:
    return await asyncio.to_thread(_download_b64_sync, url)


async def _build_input(message: discord.Message) -> str | list[dict]:
    parts: list[dict] = []
    urls = _extraer_urls(message.content)
    clean_text = re.sub(r'https?://[^\s]+', '', message.content).strip()

    if clean_text:
        parts.append({"type": "text", "text": clean_text})

    for url in urls:
        parts.append({"type": "text", "text": f"[Link: {url}]"})

    for attachment in message.attachments:
        if not attachment.content_type:
            continue
        ct = attachment.content_type

        b64, mime = await _download_file_b64(attachment.url)

        if ct.startswith("image/"):
            if b64:
                parts.append({"type": "image", "data": b64, "mime_type": mime or ct})
            else:
                parts.append({"type": "text", "text": f"[Image: {attachment.filename}]({attachment.url})"})
        elif ct == "application/pdf":
            if b64:
                parts.append({"type": "document", "data": b64, "mime_type": mime or ct})
            else:
                parts.append({"type": "text", "text": f"[PDF: {attachment.filename}]({attachment.url})"})
        elif ct.startswith("video/"):
            if b64:
                parts.append({"type": "video", "data": b64, "mime_type": mime or ct})
            else:
                parts.append({"type": "text", "text": f"[Video: {attachment.filename}]({attachment.url})"})
        elif ct.startswith("audio/"):
            if b64:
                parts.append({"type": "audio", "data": b64, "mime_type": mime or ct})
            else:
                parts.append({"type": "text", "text": f"[Audio: {attachment.filename}]({attachment.url})"})
        elif ct.startswith("text/"):
            if b64:
                plain = base64.b64decode(b64).decode("utf-8", errors="replace")[:3000]
                parts.append({"type": "text", "text": f"[{attachment.filename}]:\n{plain}"})
            else:
                text = await _fetch_url_content(attachment.url)
                if text:
                    parts.append({"type": "text", "text": f"[{attachment.filename}]:\n{text}"})
                else:
                    parts.append({"type": "text", "text": f"[File: {attachment.filename}]({attachment.url})"})
        else:
            parts.append({"type": "text", "text": f"[File: {attachment.filename}]({attachment.url})"})

    if not parts:
        return "..."

    if len(parts) == 1 and parts[0]["type"] == "text":
        return parts[0]["text"]
    return parts


# ── Error handling, commands & main loop ─────────────────────────

async def _handle_error(message: discord.Message, error: Exception):
    err = str(error).lower()
    if any(tag in err for tag in ("429", "503", "resource_exhausted")):
        match = re.search(r'retry\s+in\s+([\d.]+)s', str(error), re.IGNORECASE)
        wait = float(match.group(1)) if match else 15
        global cooldown_until
        cooldown_until = time.time() + wait + 5
        log.warning("API exhausted after retries: %s", error)
        await message.channel.send(
            f":hourglass: Model rate limited or quota exhausted. Back in {int(wait)}s."
        )
    else:
        log.error("Chat error: %s", error)
        await message.channel.send(f":x: Unexpected error: {error}")


@bot.command()
async def clean(ctx):
    if ctx.channel.id in channel_interactions:
        del channel_interactions[ctx.channel.id]
        await _save_history()
        await ctx.send(":broom: Context cleared.")
    else:
        await ctx.send(":thinking: Nothing to forget.")


@bot.command()
async def history(ctx):
    if ctx.channel.id in channel_interactions:
        await ctx.send(f":scroll: Active ID: `{channel_interactions[ctx.channel.id]}`")
    else:
        await ctx.send(":thinking: No history in this channel.")


@bot.command()
async def setchannel(ctx, option: str = None):
    if not ctx.guild:
        await ctx.send(":x: This command only works in a server.")
        return
    if option == "disable":
        if ctx.guild.id in guild_channels:
            del guild_channels[ctx.guild.id]
            await _save_channels()
            await ctx.send(":white_check_mark: Auto-response channel disabled.")
        else:
            await ctx.send(":thinking: No channel was configured.")
        return
    guild_channels[ctx.guild.id] = ctx.channel.id
    await _save_channels()
    await ctx.send(f":white_check_mark: Now auto-responding in {ctx.channel.mention}.")


def _get_user_name(message: discord.Message) -> str:
    return message.author.name if hasattr(message.author, 'name') else str(message.author)


@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)

    if message.author.bot or message.content.startswith("!"):
        return
    if not message.content.strip() and not message.attachments:
        return

    guild_ch = message.guild and guild_channels.get(message.guild.id)
    should_respond = (
        bot.user in message.mentions
        or await _is_reply_to_bot(message)
        or (guild_ch and message.channel.id == guild_ch)
    )
    if not should_respond:
        return

    global cooldown_until
    if time.time() < cooldown_until:
        return

    try:
        async with message.channel.typing():
            await _process_message(message, _get_user_name(message))
    except discord.HTTPException:
        await _process_message(message, _get_user_name(message))


async def _process_message(message: discord.Message, user_name: str):
    try:
        input_content = await _build_input(message)

        urls_in_msg = _extraer_urls(message.content)
        if urls_in_msg and not message.attachments:
            url_contents = []
            for url in urls_in_msg[:3]:
                content = await _fetch_url_content(url)
                if content:
                    url_contents.append(content)
            if url_contents:
                joined = "\n\n".join(url_contents)
                if isinstance(input_content, str):
                    input_content = f"{input_content}\n\n{joined}"
                else:
                    input_content.append({"type": "text", "text": joined})

        system_instruction = (
            "You are GeminiFake, an AI assistant integrated in Discord. "
            "You are bilingual (English/Spanish). "
            f"The user talking to you is {user_name}. "
            "Respond in English by default. If the user writes in Spanish, respond in Spanish. "
            "Be brief and direct to be fast. "
            "If they send images, describe them or answer about their content. "
            "If they send PDFs, videos or audio, analyze them as requested. "
            "If there are links and their content was provided, use it to answer. "
            f"To mention the user on Discord use {message.author.mention}. "
            "Keep a friendly tone."
        )

        last_id = channel_interactions.get(message.channel.id)

        try:
            response = await _call_with_retry(
                input_content, system_instruction, message.channel, last_id
            )
        except Exception as e:
            if last_id and "invalid" in str(e).lower():
                channel_interactions.pop(message.channel.id, None)
                await _save_history()
                response = await _call_with_retry(
                    input_content, system_instruction, message.channel, None
                )
            else:
                raise

        text = response.steps[-1].content[0].text

        if text and text.strip():
            channel_interactions[message.channel.id] = response.id
            await _send_response(message, text)
            await _save_history()
        else:
            await message.channel.send(":warning: Gemini returned no response.")

    except Exception as e:
        await _handle_error(message, e)


if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        log.info("Shutdown by user")
    finally:
        _write_history({str(k): v for k, v in channel_interactions.items()})