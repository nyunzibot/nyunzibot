import io
import asyncio
import aiohttp
import logging
import discord
import tempfile
import os
import subprocess
import imageio_ffmpeg
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


def _compress_video_files(input_path: str, output_path: str, target_size: int) -> int:
    """Returns the smallest size achieved. > target_size if failed."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # helper (integrated into main loop now)



    # Calculate compression ratio needed
    input_size = os.path.getsize(input_path)
    ratio = input_size / target_size
    
    # Define Tiers: (Label, ScaleW, CRF, Preset)
    # ScaleW=0 means original resolution (no scaling)
    tiers = [
        ("Light", 0, 23, "superfast"),       # ~1.5x reduction target
        ("Moderate", 1280, 24, "superfast"), # ~3x reduction target
        ("Aggressive", 854, 28, "ultrafast"),# ~6x reduction target
        ("Potato", 640, 32, "ultrafast"),    # ~10x reduction target
    ]

    # Select starting tier based on required ratio
    start_index = 0
    if ratio > 4.0:
        start_index = 2 # Start at Aggressive
    elif ratio > 1.5:
        start_index = 1 # Start at Moderate
    else:
        start_index = 0 # Start at Light (just over limit)

    log.info(f"[COMPRESS VIDEO] Input: {input_size} bytes (Ratio: {ratio:.2f}). Starting at Tier {start_index} ({tiers[start_index][0]})")

    best_size = 999_999_999

    for i in range(start_index, len(tiers)):
        label, scale, crf, preset = tiers[i]
        
        # If scale is 0, use -1:-1 to keep original resolution (or just don't scale? no, filter expects something)
        # Actually run_pass uses f"scale={scale_w}:-2". If 0 passed, we need logic.
        # Let's handle it inside loop:
        
        real_scale = scale
        scale_filter = f"scale={real_scale}:-2"
        if real_scale == 0:
             # Just copy raw, or use iw? using -1:-1 is safer for keeping aspect
             scale_filter = "scale=iw:-2" 

        log.info(f"[COMPRESS VIDEO] trying {label} pass (crf={crf}, preset={preset})...")
        
        cmd = [
            ffmpeg_exe, "-y",
            "-i", input_path,
            "-vf", scale_filter,
            "-vcodec", "libx264",
            "-crf", str(crf),
            "-preset", preset,
            "-acodec", "aac",
            "-b:a", "128k",
            output_path
        ]
        
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False, timeout=300, text=True, encoding='utf-8', errors='replace')
            if res.returncode != 0:
                log.warning(f"[COMPRESS VIDEO] FFmpeg error ({label}): {res.stderr[:200]}")
                continue
        except subprocess.TimeoutExpired:
            log.warning(f"[COMPRESS VIDEO] FFmpeg timeout ({label})")
            continue
        except Exception as e:
            log.warning(f"[COMPRESS VIDEO] Subprocess error ({label}): {e}")
            continue

        if os.path.exists(output_path):
            s = os.path.getsize(output_path)
            if s <= target_size:
                return s
            if s < best_size:
                best_size = s
                
            log.info(f"[COMPRESS VIDEO] {label} pass result: {s} bytes (Target: {target_size}) - Too large")
    
    return best_size


async def compress_video(raw: bytes, target_size: int = MAX_DISCORD_BYTES) -> discord.File | None:
    """Write raw to temp, compress, return discord.File or None."""
    def _work():
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_in:
                tmp_in.write(raw)
                tmp_in_path = tmp_in.name
            
            tmp_out_path = tmp_in_path + "_out.mp4"
            final_size = 0
            
            try:
                final_size = _compress_video_files(tmp_in_path, tmp_out_path, target_size)
                if final_size <= target_size:
                    # Read back
                    with open(tmp_out_path, "rb") as f:
                        processed_bytes = f.read()
                    log.info(f"[COMPRESS VIDEO] Success: {len(raw)} -> {len(processed_bytes)}")
                    return discord.File(io.BytesIO(processed_bytes), filename="action.mp4", spoiler=True)
                else:
                    log.warning(f"[COMPRESS VIDEO] Failed to compress small enough (best: {final_size} bytes)")
                    return None
            finally:
                if os.path.exists(tmp_in_path):
                    os.unlink(tmp_in_path)
                if os.path.exists(tmp_out_path):
                    os.unlink(tmp_out_path)

        except Exception as e:
            log.warning(f"[COMPRESS VIDEO] Error: {e}")
            return None

    return await asyncio.to_thread(_work)


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

    # ---- Video: attached if small, compress if large ----
    if ext in (".mp4", ".webm"):
        if len(raw) <= MAX_DISCORD_BYTES:
            buf = io.BytesIO(raw)
            buf.seek(0)
            fname = "action" + ext
            return (discord.File(buf, filename=fname, spoiler=True), fname, ProcessError.NONE)
        
        # Too large? Try compression if enabled or aggressive
        # Too large? Try compression only if aggressive (so we can notify user first)
        if not aggressive_compress:
            return (None, None, ProcessError.FILE_TOO_LARGE)

        log.info(f"[PROCESS] Video too large ({len(raw)}), attempting compression...")
        f = await compress_video(raw)
        if f:
             return (f, "action.mp4", ProcessError.NONE)
             
        log.warning(f"[PROCESS] Video compression failed (still too large or error)")
        return (None, None, ProcessError.FILE_TOO_LARGE)

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


