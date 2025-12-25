from .gelbooru import fetch_image_gelbooru
from .rule34 import fetch_image_rule34
from .rule34us import fetch_image_rule34us
from .safebooru import fetch_image_safebooru
from .konachan import fetch_image_konachan
from .yandere import fetch_image_yandere
from .danbooru import fetch_image_danbooru

# =========================
# WRAPPER: Gelbooru -> Rule34 -> Safe -> Kona -> Yande -> Dan
# =========================
async def fetch_image(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    # res = await fetch_image_gelbooru(tags, avoid_md5s)
    # if res: return res
    
    # res = await fetch_image_rule34(tags, avoid_md5s)
    # if res: return res

    res = await fetch_image_rule34us(tags, avoid_md5s)
    if res: return res
    
    res = await fetch_image_safebooru(tags, avoid_md5s)
    if res: return res
    
    res = await fetch_image_konachan(tags, avoid_md5s)
    if res: return res
    
    res = await fetch_image_yandere(tags, avoid_md5s)
    if res: return res
    
    return await fetch_image_danbooru(tags, avoid_md5s)
