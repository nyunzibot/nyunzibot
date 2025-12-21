import io
import asyncio
import aiohttp
import logging
import discord
from PIL import Image
from enum import Enum

log = logging.getLogger("nyunzi")

MAX_DISCORD_BYTES = 25_000_000
MAX_DOWNLOAD_BYTES = 40_000_000


class ProcessError(Enum):
    """Detailed error reasons for image processing failures."""
    NONE = "none"
    DOWNLOAD_FAILED = "download_failed"     # HTTP/network error
    RATE_LIMITED = "rate_limited"           # 429 response
    FILE_TOO_LARGE = "file_too_large"       # Exceeds max size
    PROCESSING_FAILED = "processing_failed" # PIL/conversion error


def _ext_from_url(url: str) -> str:
    u = (url or "").lower().split("?")[0].split("#")[0]
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm"):
        if u.endswith(ext):
            return ext
    return ""


async def process_image(url: str, max_attempts: int = 3) -> tuple[discord.File | None, str | None, ProcessError]:
    """
    Returns:
      (file_to_attach, attachment_name, error)
    If file_to_attach is None, you should send the URL as a link (video too large, etc).
    The error indicates what went wrong on failure.
    """
    if not url:
        return (None, None, ProcessError.DOWNLOAD_FAILED)

    ext = _ext_from_url(url)
    backoffs = [0.0, 1.0, 2.5, 5.0]

    # Download raw bytes (once)
    raw: bytes | None = None
    last_error = ProcessError.DOWNLOAD_FAILED
    was_rate_limited = False
    
    for attempt in range(1, max_attempts + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 429:
                        was_rate_limited = True
                        last_error = ProcessError.RATE_LIMITED
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
                    if resp.status != 200:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue

                    raw = await resp.read()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
            continue

        if raw is None:
            continue
        if len(raw) > MAX_DOWNLOAD_BYTES:
            return (None, None, ProcessError.FILE_TOO_LARGE)
        break

    if raw is None:
        if was_rate_limited:
            return (None, None, ProcessError.RATE_LIMITED)
        return (None, None, ProcessError.DOWNLOAD_FAILED)

    # ---- GIF: attach as-is (keeps animation) ----
    if ext == ".gif":
        if len(raw) > MAX_DISCORD_BYTES:
            return (None, None, ProcessError.FILE_TOO_LARGE)
        buf = io.BytesIO(raw)
        buf.seek(0)
        return (discord.File(buf, filename="action.gif", spoiler=True), "action.gif", ProcessError.NONE)

    # ---- Video: try attach if small, else send link ----
    if ext in (".mp4", ".webm"):
        if len(raw) > MAX_DISCORD_BYTES:
            return (None, None, ProcessError.FILE_TOO_LARGE)
        buf = io.BytesIO(raw)
        buf.seek(0)
        fname = "action" + ext
        return (discord.File(buf, filename=fname, spoiler=True), fname, ProcessError.NONE)

    # ---- Images: convert to JPEG like before ----
    def pil_work(b: bytes) -> discord.File | None:
        try:
            image = Image.open(io.BytesIO(b)).convert("RGB")
            image.thumbnail((2048, 2048))

            out = io.BytesIO()
            image.save(out, format="JPEG", quality=85, optimize=True)
            out.seek(0)

            if out.getbuffer().nbytes > MAX_DISCORD_BYTES:
                return None

            return discord.File(out, filename="action.jpg", spoiler=True)
        except Exception as e:
            log.warning("[IMG PROCESS] PIL error: %s: %s", type(e).__name__, e)
            return None

    f = await asyncio.to_thread(pil_work, raw)
    if not f:
        return (None, None, ProcessError.PROCESSING_FAILED)
    return (f, "action.jpg", ProcessError.NONE)

