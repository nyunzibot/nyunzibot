from .gelbooru import fetch_image_gelbooru
from .rule34 import fetch_image_rule34

# =========================
# WRAPPER: Gelbooru -> Rule34
# =========================
async def fetch_image(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    res = await fetch_image_gelbooru(tags, avoid_md5s)
    if res:
        return res
    return await fetch_image_rule34(tags, avoid_md5s)
