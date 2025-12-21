import io
import asyncio
import aiohttp
import logging
import discord
from PIL import Image
from enum import Enum

log = logging.getLogger("nyunzi")

MAX_DISCORD_BYTES = 25_000_000
MAX_DOWNLOAD_BYTES = 500_000_000


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


async def compress_image(raw: bytes, target_size: int = MAX_DISCORD_BYTES) -> discord.File | None:
    """
    Aggressively compress an image to fit within target_size.
    Tries progressively lower quality and smaller dimensions.
    Returns discord.File or None if compression fails.
    """
    def _compress(b: bytes) -> discord.File | None:
        try:
            # Try progressively more aggressive compression
            quality_levels = [75, 60, 45, 30, 20]
            max_dims = [(2048, 2048), (1600, 1600), (1200, 1200), (800, 800), (600, 600)]
            
            for quality, dims in zip(quality_levels, max_dims):
                image = Image.open(io.BytesIO(b)).convert("RGB")
                image.thumbnail(dims)
                
                out = io.BytesIO()
                image.save(out, format="JPEG", quality=quality, optimize=True)
                out.seek(0)
                
                if out.getbuffer().nbytes <= target_size:
                    log.info(f"[COMPRESS] Success at quality={quality}, dims={dims}, size={out.getbuffer().nbytes}")
                    return discord.File(out, filename="action.jpg", spoiler=True)
            
            log.warning("[COMPRESS] Could not compress image small enough")
            return None
        except Exception as e:
            log.warning(f"[COMPRESS] PIL error: {type(e).__name__}: {e}")
            return None
    
    return await asyncio.to_thread(_compress, raw)


async def process_image(url: str, max_attempts: int = 3, aggressive_compress: bool = False) -> tuple[discord.File | None, str | None, ProcessError]:
    """
    Returns:
      (file_to_attach, attachment_name, error)
    If file_to_attach is None, you should send the URL as a link (video too large, etc).
    The error indicates what went wrong on failure.
    
    If aggressive_compress=True, will try harder to compress oversized images.
    """
    if not url:
        log.warning("[PROCESS] No URL provided")
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
                        log.warning(f"[PROCESS] Rate limited (429) on attempt {attempt}/{max_attempts}: {url[:80]}")
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
                    if resp.status != 200:
                        log.warning(f"[PROCESS] HTTP {resp.status} on attempt {attempt}/{max_attempts}: {url[:80]}")
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue

                    raw = await resp.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.warning(f"[PROCESS] Download error on attempt {attempt}/{max_attempts}: {type(e).__name__}")
            await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
            continue

        if raw is None:
            continue
        if len(raw) > MAX_DOWNLOAD_BYTES:
            log.warning(f"[PROCESS] File too large to download: {len(raw)} bytes > {MAX_DOWNLOAD_BYTES}")
            return (None, None, ProcessError.FILE_TOO_LARGE)
        break

    if raw is None:
        if was_rate_limited:
            log.warning(f"[PROCESS] Rate limited, exhausted retries: {url[:80]}")
            return (None, None, ProcessError.RATE_LIMITED)
        log.warning(f"[PROCESS] Download failed after {max_attempts} attempts: {url[:80]}")
        return (None, None, ProcessError.DOWNLOAD_FAILED)

    # ---- GIF: attach as-is (keeps animation) ----
    if ext == ".gif":
        if len(raw) > MAX_DISCORD_BYTES:
            log.warning(f"[PROCESS] GIF too large: {len(raw)} bytes")
            return (None, None, ProcessError.FILE_TOO_LARGE)
        buf = io.BytesIO(raw)
        buf.seek(0)
        return (discord.File(buf, filename="action.gif", spoiler=True), "action.gif", ProcessError.NONE)

    # ---- Video: try attach if small, else fail (can't compress easily) ----
    if ext in (".mp4", ".webm"):
        if len(raw) > MAX_DISCORD_BYTES:
            log.warning(f"[PROCESS] Video too large: {len(raw)} bytes")
            return (None, None, ProcessError.FILE_TOO_LARGE)
        buf = io.BytesIO(raw)
        buf.seek(0)
        fname = "action" + ext
        return (discord.File(buf, filename=fname, spoiler=True), fname, ProcessError.NONE)

    # ---- Images: convert to JPEG ----
    def pil_work(b: bytes, compress_hard: bool) -> discord.File | None:
        try:
            image = Image.open(io.BytesIO(b)).convert("RGB")
            
            if compress_hard:
                # More aggressive compression
                image.thumbnail((1600, 1600))
                quality = 70
            else:
                image.thumbnail((2048, 2048))
                quality = 85

            out = io.BytesIO()
            image.save(out, format="JPEG", quality=quality, optimize=True)
            out.seek(0)

            if out.getbuffer().nbytes > MAX_DISCORD_BYTES:
                return None

            return discord.File(out, filename="action.jpg", spoiler=True)
        except Exception as e:
            log.warning("[PROCESS] PIL error: %s: %s", type(e).__name__, e)
            return None

    f = await asyncio.to_thread(pil_work, raw, aggressive_compress)
    
    # If normal processing failed and we haven't tried aggressive compression, try it
    if not f and not aggressive_compress:
        log.info("[PROCESS] Normal processing failed, trying aggressive compression")
        f = await compress_image(raw)
        if f:
            return (f, "action.jpg", ProcessError.NONE)
    
    if not f:
        log.warning(f"[PROCESS] Processing failed for: {url[:80]}")
        return (None, None, ProcessError.PROCESSING_FAILED)
    return (f, "action.jpg", ProcessError.NONE)


