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


async def fetch_post_by_id(post_id: int, site: str = "gelbooru", pages: list[int] | None = None) -> list[tuple[str, str]] | None:
    """
    Fetch a single post by ID from a specific site.
    Returns list of (file_url, md5) or None if not found.
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
                
                results = []
                
                # Check if multi-page
                meta_pages = illust.get('meta_pages') or []
                is_multi = len(meta_pages) > 0
                
                target_pages = pages if pages is not None else [0]
                
                if is_multi:
                    for p_idx in target_pages:
                        if p_idx < len(meta_pages):
                            url = meta_pages[p_idx]['image_urls']['original']
                            pseudo_hash = f"pixiv_{post_id}_p{p_idx}"
                            results.append((url, pseudo_hash))
                else:
                    # Single page
                    # Only valid if asking for page 0
                    if 0 in target_pages:
                        url = None
                        if illust.get('meta_single_page', {}).get('original_image_url'):
                            url = illust['meta_single_page']['original_image_url']
                        elif illust.get('image_urls', {}).get('large'):
                            url = illust['image_urls']['large']
                        
                        if url:
                            results.append((url, f"pixiv_{post_id}_p0"))
                            
                return results if results else None
            
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
                return [(file_url, md5 or str(post_id))]
                
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
    
    
    # Normalize items to list of {'id': [ids], 'site': 'site_name', 'pages': [pages per id?]}
    candidates = []
    
    for item in items:
        # Debug item structure (print first one)
        # print(f"DEBUG item: {item}")
        # Default structure
        target_ids = []
        target_site = "gelbooru"
        target_pages = None # list of list of pages, or None
        
        if isinstance(item, dict):
            # Format: {'id': ..., 'site': ..., 'pages': ...}
            raw_id = item.get("id")
            target_site = item.get("site", "gelbooru")
            
            raw_pages = item.get("pages")
            
            if isinstance(raw_id, list):
                target_ids = raw_id
                if raw_pages and isinstance(raw_pages, list):
                     target_pages = raw_pages 
            else:
                target_ids = [raw_id]
                if raw_pages:
                    target_pages = [raw_pages] # Wrap in list to match target_ids[0]
                    
        elif isinstance(item, list):
             # Legacy list of IDs -> Gelbooru
             target_ids = item
        else:
             # Legacy single ID -> Gelbooru
             target_ids = [item]
             
        if target_ids:
            # Check for None items (bug fix for int(None) error seen in logs)
            target_ids = [tid for tid in target_ids if tid is not None]
            
            if target_ids:
                candidates.append({
                    'ids': target_ids, 
                    'site': target_site,
                    'pages': target_pages
                })
    
    if not candidates:
        return None

    # Try up to 5 times to find a preselected image we haven't seen
    random.shuffle(candidates)
    
    for cand in candidates[:5]:
        picked_ids = cand['ids']
        site = cand['site']
        pages_list = cand.get('pages') # list of page-lists corresponding to picked_ids, or None
        
        group_fetched_successfully = True
        temp_urls = []
        temp_first_md5 = None
        
        for i, post_id in enumerate(picked_ids):
            # Determine pages for this specific post_id
            current_pages = None
            if pages_list and i < len(pages_list):
                current_pages = pages_list[i]
            
            result = await fetch_post_by_id(int(post_id), site=site, pages=current_pages)
            # If any fetch in a group fails, we abandon the group
            if not result:
                group_fetched_successfully = False
                break
                
            # result is list of (url, md5)
            for r_url, r_md5 in result:
                temp_urls.append(r_url)
                if temp_first_md5 is None:
                    temp_first_md5 = r_md5
        
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
