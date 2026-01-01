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
    
    candidate_lists = []
    # Flatten the structure slightly for random picking
    # We don't filter by ID anymore because we need the MD5 to know if we've seen it
    for item in items:
        if isinstance(item, list):
            candidate_lists.append(item)
        else:
            candidate_lists.append([item])
    
    if not candidate_lists:
        return None

    # Try up to 5 times to find a preselected image we haven't seen
    # We shuffle to randomize the check order
    random.shuffle(candidate_lists)
    
    for picked_ids in candidate_lists[:5]:
        # Fetch all posts by ID for this candidate group
        urls = []
        first_md5 = None
        
        # We need to fetch ALL images in the group to get their MD5s
        # If ANY of them are seen, we should probably skip the whole group to be safe?
        # Or just check the first one as the representative for the group?
        # The calling code uses the returned MD5 (single) to track the "pair/action"
        
        group_fetched_successfully = True
        temp_urls = []
        temp_first_md5 = None
        
        for i, post_id in enumerate(picked_ids):
            result = await fetch_post_by_id(int(post_id))
            if not result:
                group_fetched_successfully = False
                break
                
            file_url, md5 = result
            temp_urls.append(file_url)
            if i == 0:
                temp_first_md5 = md5
        
        if not group_fetched_successfully:
            continue
            
        # Now check if we've seen this group (using first image's MD5 as key)
        if temp_first_md5 and temp_first_md5 in avoid_md5s:
            log.info(f"[PRESELECTED] Skipping group starting with {picked_ids[0]} (MD5 {temp_first_md5} seen)")
            continue
            
        # Found a valid one!
        urls = temp_urls
        md5_id = temp_first_md5 or str(picked_ids[0])
        
        log.info(f"[PRESELECTED] Returning {len(urls)} image(s) for category={category}")
        return (urls, md5_id, "gelbooru")
    
    log.info(f"[PRESELECTED] No unseen preselected images found for category={category}")
    return None
