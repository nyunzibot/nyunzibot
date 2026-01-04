from .gelbooru import fetch_image_gelbooru
from .rule34 import fetch_image_rule34
from .rule34us import fetch_image_rule34us
from .rule34video import fetch_image_rule34video
from .safebooru import fetch_image_safebooru
from .konachan import fetch_image_konachan
from .yandere import fetch_image_yandere
from .danbooru import fetch_image_danbooru
from .pixiv import fetch_image_pixiv

import config

# =========================
# WRAPPER: Gelbooru -> Rule34 -> Safe -> Kona -> Yande -> Dan -> Pixiv
# =========================
async def fetch_image(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    if config.ENABLE_GELBOORU:
        res = await fetch_image_gelbooru(tags, avoid_md5s)
        if res: return res
    
    if config.ENABLE_RULE34:
        res = await fetch_image_rule34(tags, avoid_md5s)
        if res: return res

    if config.ENABLE_RULE34US:
        res = await fetch_image_rule34us(tags, avoid_md5s)
        if res: return res

    if config.ENABLE_RULE34VIDEO:
        res = await fetch_image_rule34video(tags, avoid_md5s)
        if res: return res
    
    if config.ENABLE_SAFEBOORU:
        res = await fetch_image_safebooru(tags, avoid_md5s)
        if res: return res
    
    if config.ENABLE_KONACHAN:
        res = await fetch_image_konachan(tags, avoid_md5s)
        if res: return res
    
    if config.ENABLE_YANDERE:
        res = await fetch_image_yandere(tags, avoid_md5s)
        if res: return res
    
    if config.ENABLE_DANBOORU:
        res = await fetch_image_danbooru(tags, avoid_md5s)
        if res: return res
    
    if config.ENABLE_PIXIV:
        return await fetch_image_pixiv(tags, avoid_md5s)
    
    return None
