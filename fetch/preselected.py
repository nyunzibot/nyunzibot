"""
Preselected image fetcher - fetches images by Gelbooru post ID.
"""
import random
import aiohttp
import asyncio
import logging
from typing import Optional
from tags.preselected import PRESELECTED_SFW
from config import GELBOORU_API, GELBOORU_API_KEY, GELBOORU_USER_ID, USER_AGENT

log = logging.getLogger("nyunzi")


async def fetch_post_by_id(post_id: int) -> tuple[str, str] | None:
    """
    Fetch a single Gelbooru post by ID.
    Returns (file_url, md5) or None if not found.
    """
    if not (GELBOORU_API_KEY and GELBOORU_USER_ID):
        log.warning("[PRESELECTED] Gelbooru API credentials not configured")
        return None
    
    params = {
        "id": post_id,
        "limit": 1,
        "api_key": GELBOORU_API_KEY,
        "user_id": GELBOORU_USER_ID,
        "json": 1,
    }
    
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(
                GELBOORU_API,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    log.warning(f"[PRESELECTED] Gelbooru API returned {resp.status} for id={post_id}")
                    return None
                
                data = await resp.json(content_type=None)
                
                # Extract post from response
                posts = None
                if isinstance(data, dict):
                    posts = data.get("post")
                elif isinstance(data, list):
                    posts = data
                
                if not posts:
                    log.warning(f"[PRESELECTED] No post found for id={post_id}")
                    return None
                
                if isinstance(posts, list):
                    post = posts[0] if posts else None
                else:
                    post = posts
                
                if not post or not isinstance(post, dict):
                    return None
                
                file_url = post.get("file_url")
                md5 = post.get("md5")
                
                if not file_url:
                    log.warning(f"[PRESELECTED] No file_url for id={post_id}")
                    return None
                
                log.info(f"[PRESELECTED] Fetched id={post_id} -> {file_url}")
                return (file_url, md5 or str(post_id))
                
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.warning(f"[PRESELECTED] Failed to fetch id={post_id}: {e}")
        return None
    except Exception as e:
        log.error(f"[PRESELECTED] Error fetching id={post_id}: {e}")
        return None


async def fetch_preselected(category: str, avoid_md5s: set[str]) -> tuple[list[str], str, str] | None:
    """
    Fetches preselected image(s) by Gelbooru post ID for the given category.
    Returns (urls, md5, site) if found and not in avoid list.
    - urls: list of image URLs (single image = list of one)
    - md5: identifier for deduplication (first post's md5)
    - site: "preselected"
    """
    if not category or category not in PRESELECTED_SFW:
        return None
        
    items = PRESELECTED_SFW[category]
    if not items:
        return None
    
    # Filter out ones we've seen (using md5/id as identifier)
    # We need to check against the string version of IDs since avoid_md5s may contain both
    candidates = []
    for item in items:
        if isinstance(item, list):
            # It's a group of IDs - use first ID as the identifier
            if item and str(item[0]) not in avoid_md5s:
                candidates.append(item)
        else:
            # Single ID
            if str(item) not in avoid_md5s:
                candidates.append([item])  # Wrap in list for consistent handling
    
    if not candidates:
        return None
    
    # Pick a random candidate
    picked_ids = random.choice(candidates)
    
    # Fetch all posts by ID
    urls = []
    first_md5 = None
    
    for post_id in picked_ids:
        result = await fetch_post_by_id(int(post_id))
        if result:
            file_url, md5 = result
            urls.append(file_url)
            if first_md5 is None:
                first_md5 = md5
    
    if not urls:
        log.warning(f"[PRESELECTED] All fetches failed for category={category}")
        return None
    
    # Use first md5 as the dedup identifier
    md5_id = first_md5 or str(picked_ids[0])
    
    log.info(f"[PRESELECTED] Returning {len(urls)} image(s) for category={category}")
    return (urls, md5_id, "preselected")
