import io
import asyncio
import aiohttp
import logging
import discord
from PIL import Image

log = logging.getLogger("nyunzi")

# =========================
# IMAGE DOWNLOAD + PIL CONVERT (OFF LOOP)
# =========================
async def process_image(url: str, max_attempts: int = 3) -> discord.File | None:
    if not url:
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]

    def pil_work(raw_bytes: bytes) -> discord.File | None:
        try:
            image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            image.thumbnail((2048, 2048))

            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=85, optimize=True)
            buf.seek(0)

            if buf.getbuffer().nbytes > 8_000_000:
                return None

            return discord.File(buf, filename="action.jpg", spoiler=True)
        except Exception as e:
            log.warning("[IMG PROCESS] PIL error: %s: %s", type(e).__name__, e)
            return None

    for attempt in range(1, max_attempts + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    log.info("[IMG FETCH] attempt=%s/%s status=%s", attempt, max_attempts, resp.status)

                    if resp.status == 429:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
                    if resp.status != 200:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue

                    raw = await resp.read()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            log.info("[IMG FETCH] exception=%s: %s — sleeping %ss", type(e).__name__, e, wait)
            await asyncio.sleep(wait)
            continue

        if len(raw) > 24_000_000:
            return None

        return await asyncio.to_thread(pil_work, raw)

    return None
