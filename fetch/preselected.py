"""
Preselected image fetcher - fetches images by Post ID from various boorus.
"""
import random
import aiohttp
import asyncio
import logging
from typing import Optional, Any
from tags.preselected import PRESELECTED_SFW
from config import (
    GELBOORU_API, GELBOORU_API_KEY, GELBOORU_USER_ID,
    SAFEBOORU_API,
    RULE34_API,
    KONACHAN_API,
    YANDERE_API,
    DANBOORU_API,
    USER_AGENT,
    PIXIV_REFRESH_TOKEN
)
try:
    from pixivpy_async import AppPixivAPI
except ImportError:
    AppPixivAPI = None


log = logging.getLogger("nyunzi")


async def fetch_post_by_id(post_id: int, site: str = "gelbooru") -> tuple[str, str] | None:
    """
    Fetch a single post by ID from a specific site.
    Returns (file_url, md5) or None if not found.
    """
    url = ""
    params: dict[str, Any] = {}
    
    # --- Configuration per site ---
    if site == "gelbooru":
        url = GELBOORU_API
        params = {
            "id": post_id,
            "limit": 1,
            "api_key": GELBOORU_API_KEY,
            "user_id": GELBOORU_USER_ID,
            "json": 1,
        }
    elif site == "safebooru":
        # Safebooru DAPI
        url = SAFEBOORU_API
        params = {
            "id": post_id,
            "json": 1,
        }
    elif site == "rule34":
        # Rule34 DAPI
        url = RULE34_API
        params = {
            "id": post_id,
            "json": 1,
        }
    elif site == "konachan":
        # Moebooru: uses /post.json with tags=id:X
        url = f"{KONACHAN_API}.json"
        params = {
            "tags": f"id:{post_id}",
            "limit": 1,
        }
    elif site == "yandere":
        # Moebooru: uses /post.json with tags=id:X
        url = f"{YANDERE_API}.json"
        params = {
            "tags": f"id:{post_id}",
            "limit": 1,
        }
    elif site == "danbooru":
        # Danbooru: /posts/{id}.json
        url = f"{DANBOORU_API}/posts/{post_id}.json"
        params = {}
    elif site == "pixiv":
        if not AppPixivAPI:
             log.error("[PRESELECTED] pixivpy_async not installed, cannot fetch Pixiv.")
             return None
        if not PIXIV_REFRESH_TOKEN:
             log.warning("[PRESELECTED] No PIXIV_REFRESH_TOKEN, skipping Pixiv.")
             return None
             
        # Pixiv logic is different (uses pixivpy, not simple HTTP dict)
        try:
            api = AppPixivAPI()
            await api.login(refresh_token=PIXIV_REFRESH_TOKEN)
            
            json_result = await api.illust_detail(post_id)
            
            # Clean up immediately
            try:
                await api.client.close()
            except Exception:
                pass
                
            if json_result and 'illust' in json_result:
                illust = json_result['illust']
                
                # Check if ugoira (animated) - not supported for standard image embeds usually, return zip?
                # For now, treat everything as image.
                
                image_url = None
                if illust.get('meta_single_page', {}).get('original_image_url'):
                    image_url = illust['meta_single_page']['original_image_url']
                elif illust.get('meta_pages'):
                     image_url = illust['meta_pages'][0]['image_urls']['original']
                elif illust.get('image_urls', {}).get('large'):
                    image_url = illust['image_urls']['large']
                    
                if image_url:
                    # Pixiv uses id as hash/md5 effectively
                    return (image_url, f"pixiv_{post_id}")
            
            return None
            
        except Exception as e:
            log.warning(f"[PRESELECTED] Pixiv fetch failed for {post_id}: {e}")
            return None

    else:
        log.warning(f"[PRESELECTED] Unknown site '{site}'")
        return None
    
    # --- Fetching ---
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    log.warning(f"[PRESELECTED] {site} API returned {resp.status} for id={post_id}")
                    return None
                
                # Check for empty response content (Safebooru sometimes does this)
                if resp.content_length == 0:
                    return None

                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    return None
                
                if not data:
                    return None

                # --- Parsing response per site type ---
                post = None
                
                # Danbooru (returns single dict object)
                if site == "danbooru":
                    if isinstance(data, dict):
                        post = data
                
                # Moebooru (Konachan, Yandere) returns list
                elif site in ("konachan", "yandere"):
                    if isinstance(data, list) and len(data) > 0:
                        post = data[0]

                # Gelbooru / Safebooru / Rule34 (DAPI)
                else:
                    # Gelbooru format: {'post': [...]} or [...]
                    posts = None
                    if isinstance(data, dict):
                        posts = data.get("post") or data  # Handle different JSON structures
                    elif isinstance(data, list):
                        posts = data
                    
                    if isinstance(posts, list) and len(posts) > 0:
                        post = posts[0]
                    elif isinstance(posts, dict):
                        post = posts

                if not post or not isinstance(post, dict):
                    return None
                
                # Extract fields
                file_url = post.get("file_url") or post.get("large_file_url")
                md5 = post.get("md5") or post.get("hash")  # Safebooru uses 'hash'
                
                # Site-specific fixups
                if site == "safebooru" and not file_url:
                    directory = post.get("directory")
                    image = post.get("image")
                    if directory and image:
                        file_url = f"https://safebooru.org/images/{directory}/{image}"
                
                # Some sites return relative URLs? (usually not valid DAPI, but good to check)
                if not file_url:
                    log.warning(f"[PRESELECTED] No file_url for {site} id={post_id}")
                    return None
                
                log.info(f"[PRESELECTED] Fetched {site} id={post_id} -> {file_url}")
                return (file_url, md5 or str(post_id))
                
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.warning(f"[PRESELECTED] Failed to fetch {site} id={post_id}: {e}")
        return None
    except Exception as e:
        log.error(f"[PRESELECTED] Error fetching {site} id={post_id}: {e}")
        return None


async def fetch_preselected(category: str, avoid_md5s: set[str]) -> tuple[list[str], str, str] | None:
    """
    Fetches preselected image(s) by post ID for the given category.
    Returns (urls, md5, site) if found and not in avoid list.
    - urls: list of image URLs (single image = list of one)
    - md5: identifier for deduplication (first post's md5)
    - site: site name (e.g., "gelbooru", "safebooru")
    """
    if not category or category not in PRESELECTED_SFW:
        return None
        
    items = PRESELECTED_SFW[category]
    if not items:
        return None
    
    # Normalize items to list of {'id': [ids], 'site': 'site_name'}
    candidates = []
    
    for item in items:
        # Default structure
        target_ids = []
        target_site = "gelbooru"
        
        if isinstance(item, dict):
            # New format: {'id': ..., 'site': ...}
            raw_id = item.get("id")
            target_site = item.get("site", "gelbooru")
            
            if isinstance(raw_id, list):
                target_ids = raw_id
            else:
                target_ids = [raw_id]
        elif isinstance(item, list):
             # Legacy list of IDs -> Gelbooru
             target_ids = item
        else:
             # Legacy single ID -> Gelbooru
             target_ids = [item]
             
        if target_ids:
            candidates.append({'ids': target_ids, 'site': target_site})
    
    if not candidates:
        return None

    # Try up to 5 times to find a preselected image we haven't seen
    random.shuffle(candidates)
    
    for cand in candidates[:5]:
        picked_ids = cand['ids']
        site = cand['site']
        
        group_fetched_successfully = True
        temp_urls = []
        temp_first_md5 = None
        
        for i, post_id in enumerate(picked_ids):
            result = await fetch_post_by_id(int(post_id), site=site)
            # If any fetch in a group fails, we abandon the group
            if not result:
                group_fetched_successfully = False
                break
                
            file_url, md5 = result
            temp_urls.append(file_url)
            if i == 0:
                temp_first_md5 = md5
        
        if not group_fetched_successfully:
            continue
            
        # check if seen
        if temp_first_md5 and temp_first_md5 in avoid_md5s:
            log.info(f"[PRESELECTED] Skipping group starting with {picked_ids[0]} (MD5 {temp_first_md5} seen)")
            continue
            
        # Found it
        urls = temp_urls
        md5_id = temp_first_md5 or str(picked_ids[0])
        
        log.info(f"[PRESELECTED] Returning {len(urls)} image(s) for category={category} from {site}")
        return (urls, md5_id, site)
    
    log.info(f"[PRESELECTED] No unseen preselected images found for category={category}")
    return None
