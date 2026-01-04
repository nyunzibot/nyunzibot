import random
import logging
from urllib.parse import urlencode
from pixivpy_async import AppPixivAPI

import config
from .common import is_supported_file_url

log = logging.getLogger("nyunzi")


async def fetch_image_pixiv(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    """
    Fetcher for Pixiv using pixivpy-async.
    Note: Pixiv requires a refresh token for authentication.
    """
    if not config.PIXIV_REFRESH_TOKEN:
        log.warning("[PIXIV] No refresh token configured, skipping")
        return None

    api = AppPixivAPI()
    
    try:
        # Authenticate with refresh token
        await api.login(refresh_token=config.PIXIV_REFRESH_TOKEN)
    except Exception as e:
        log.warning(f"[PIXIV] Login failed: {e}")
        return None

    MAX_ATTEMPTS = 4

    try:
        for attempt in range(MAX_ATTEMPTS):
            try:
                # Convert booru-style tags to Pixiv search query
                # Replace underscores with spaces for Pixiv
                search_query = tags.replace("_", " ").replace("+", " ")
                
                # Random offset for variety
                offset = random.randint(0, 100)
                
                # Search for illustrations
                params = {
                    "word": search_query,
                    "search_target": "partial_match_for_tags",
                    "sort": "popular_desc",
                    "offset": offset
                }
                full_url = f"https://app-api.pixiv.net/v1/search/illust?{urlencode(params)}"
                log.info(f"[PIXIV] CALL search_illust: {full_url}")
                results = await api.search_illust(
                    word=search_query,
                    search_target="partial_match_for_tags",
                    sort="popular_desc",
                    offset=offset
                )
                
                if not results or "illusts" not in results or not results["illusts"]:
                    log.info(f"[PIXIV] No results for query={search_query} offset={offset}")
                    continue
                
                illusts = results["illusts"]
                random.shuffle(illusts)
                
                for illust in illusts:
                    # Skip manga/ugoira (animated), we want single images or first page
                    if illust.get("type") == "ugoira":
                        continue
                    
                    # Get image URL
                    if illust.get("meta_single_page", {}).get("original_image_url"):
                        image_url = illust["meta_single_page"]["original_image_url"]
                    elif illust.get("meta_pages") and len(illust["meta_pages"]) > 0:
                        # Multi-page, get first page
                        image_url = illust["meta_pages"][0].get("image_urls", {}).get("original")
                    else:
                        # Fallback to large size
                        image_url = illust.get("image_urls", {}).get("large")
                    
                    if not image_url:
                        continue
                    
                    if not is_supported_file_url(image_url):
                        continue
                    
                    # Pixiv doesn't use MD5 in URLs, use illust ID as pseudo-hash
                    pseudo_md5 = f"pixiv_{illust['id']}"
                    
                    if pseudo_md5 in avoid_md5s:
                        continue
                    
                    log.info(f"[PIXIV] Picked {image_url} (id={illust['id']})")
                    return (image_url, pseudo_md5, "pixiv")
                    
            except Exception as e:
                log.warning(f"[PIXIV] Search error: {e}")
                continue
    finally:
        # Clean up the API session
        try:
            await api.client.close()
        except Exception:
            pass

    return None
