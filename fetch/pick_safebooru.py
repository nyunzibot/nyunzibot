"""
SFW pick module for cuddle command.
This module provides image fetching from all booru sites with rating:safe filter.
"""

from enum import Enum
import logging
from typing import Callable, Awaitable, Optional
from config import DEDUP_PULL_TRIES
from .fetch_image import fetch_image  # Use all sites, not just Safebooru
from db.stats import InteractionSeen
from db.runtime import STATS_DB
from images.process import process_image, ProcessError
from .preselected import fetch_preselected
import time

log = logging.getLogger("nyunzi")


class FetchError(Enum):
    """Detailed error reasons for fetch failures."""
    NONE = "none"
    NO_RESULTS = "no_results"           # No images found for tags
    ALL_SEEN = "all_seen"               # All results were already seen
    DOWNLOAD_FAILED = "download_failed" # Couldn't download the image
    RATE_LIMITED = "rate_limited"       # API rate limit hit
    FILE_TOO_LARGE = "file_too_large"   # File exceeds Discord's limit
    PROCESSING_FAILED = "processing_failed"  # Image processing error
    VIDEO_TOO_LARGE = "video_too_large"  # Video specifically too large
    ALL_APIS_FAILED = "all_apis_failed"  # All booru APIs returned no results


def get_error_message(error: FetchError) -> str:
    """Convert FetchError to user-friendly message."""
    messages = {
        FetchError.NONE: "",
        FetchError.NO_RESULTS: "No matching SFW images found for those tags 🔍",
        FetchError.ALL_SEEN: "You've seen all the images! Try different tags 🎲",
        FetchError.DOWNLOAD_FAILED: "Couldn't download the image (server issue) 🌐",
        FetchError.RATE_LIMITED: "API rate limit hit. Wait a moment and try again ⏳",
        FetchError.FILE_TOO_LARGE: "Image was too large for Discord (>25MB) 📦",
        FetchError.PROCESSING_FAILED: "Couldn't process the image 🖼️",
        FetchError.VIDEO_TOO_LARGE: "Video was too large to attach (>25MB) 🎬",
        FetchError.ALL_APIS_FAILED: "Couldn't find any matching SFW images. Try different tags 🔄",
    }
    return messages.get(error, "Something went wrong 😭 Try again.")


def is_video_url(url: str) -> bool:
    u = (url or "").lower().split("?")[0].split("#")[0]
    return u.endswith((".mp4", ".webm"))


async def pick_media_sfw(tags, seen, *, tries: int = 8, status_cb: Optional[Callable[[str], Awaitable[None]]] = None, category: Optional[str] = None):
    """
    SFW version of pick_media - uses all booru sites with rating:safe tag.
    Returns: (image_url_or_urls, md5, site, file_or_files, fname_or_fnames, error) tuple
    
    On success: (url/urls, md5, site, file/files, fname/fnames, FetchError.NONE)
    - For multi-image preselected: url is list[str], files is list, fnames is list
    - For single image: url is str, file is single, fname is single
    On failure: (None, None, None, None, None, FetchError.<reason>)
    """
    start_time = time.time()
    last_error = FetchError.ALL_APIS_FAILED
    
    for attempt in range(tries):
        # Check overall timeout (12 minutes) to prevent Discord 401 (15 min limit)
        if time.time() - start_time > 720: 
            log.warning(f"[PICK_MEDIA_SFW] Time limit reached ({int(time.time() - start_time)}s), stopping retries")
            if 'image_url' in locals() and image_url:
                 log.info(f"[PICK_MEDIA_SFW] Falling back to URL due to timeout")
                 return (image_url, md5, site, None, None, FetchError.NONE)
            break

        picked, fetch_error = await pick_image_sfw(tags, seen, category=category)
        if not picked:
            last_error = fetch_error
            log.warning(f"[PICK_MEDIA_SFW] No image picked on attempt {attempt+1}/{tries}: {fetch_error.value}")
            return (None, None, None, None, None, last_error)

        url_or_urls, md5, site = picked
        
        # Handle multi-image case (list of URLs from preselected)
        if isinstance(url_or_urls, list):
            log.info(f"[PICK_MEDIA_SFW] Processing {len(url_or_urls)} preselected images from {site}")
            files = []
            fnames = []
            all_success = True
            
            for img_url in url_or_urls:
                file, fname, process_error = await process_image(img_url, max_attempts=3, spoiler=False)
                if file and fname:
                    files.append(file)
                    fnames.append(fname)
                else:
                    log.warning(f"[PICK_MEDIA_SFW] Failed to process one of the multi-images: {img_url}")
                    all_success = False
            
            if files:
                # Return whatever we successfully processed (may be partial)
                log.info(f"[PICK_MEDIA_SFW] Successfully processed {len(files)}/{len(url_or_urls)} images")
                return (url_or_urls, md5, site, files, fnames, FetchError.NONE)
            else:
                # All failed - fall back to URLs
                log.warning(f"[PICK_MEDIA_SFW] All multi-image processing failed, falling back to URLs")
                return (url_or_urls, md5, site, None, None, FetchError.NONE)
        
        # Single image case (original logic)
        image_url = url_or_urls
        log.info(f"[PICK_MEDIA_SFW] Attempt {attempt+1}/{tries}: Picked image from {site}")
        
        # First attempt at processing - SFW content is not spoilered
        file, fname, process_error = await process_image(image_url, max_attempts=3, spoiler=False)

        # If first attempt succeeded, we're done!
        if file and fname:
            log.info(f"[PICK_MEDIA_SFW] Success on attempt {attempt+1}/{tries}")
            return (image_url, md5, site, file, fname, FetchError.NONE)
        
        # Handle specific errors with smart retries
        if process_error == ProcessError.RATE_LIMITED:
            log.warning(f"[PICK_MEDIA_SFW] Rate limited, cannot retry")
            return (None, None, None, None, None, FetchError.RATE_LIMITED)
        
        if process_error == ProcessError.DOWNLOAD_FAILED:
            log.info(f"[PICK_MEDIA_SFW] Download failed, retrying download...")
            file, fname, process_error = await process_image(image_url, max_attempts=5, spoiler=False)
            if file and fname:
                log.info(f"[PICK_MEDIA_SFW] Download retry succeeded!")
                return (image_url, md5, site, file, fname, FetchError.NONE)
            log.warning(f"[PICK_MEDIA_SFW] Download retry also failed, trying different image")
            last_error = FetchError.DOWNLOAD_FAILED
        
        elif process_error == ProcessError.PROCESSING_FAILED:
            log.info(f"[PICK_MEDIA_SFW] Processing failed, retrying with compression...")
            file, fname, process_error = await process_image(image_url, max_attempts=3, aggressive_compress=True, spoiler=False)
            if file and fname:
                log.info(f"[PICK_MEDIA_SFW] Processing retry with compression succeeded!")
                return (image_url, md5, site, file, fname, FetchError.NONE)
            log.warning(f"[PICK_MEDIA_SFW] Processing retry also failed, trying different image")
            last_error = FetchError.PROCESSING_FAILED
        
        elif process_error == ProcessError.FILE_TOO_LARGE:
            log.info(f"[PICK_MEDIA_SFW] File too large, trying compression...")
            if status_cb:
                await status_cb("<a:loading:1453449271839031487> Compressing...")
            
            file, fname, process_error = await process_image(image_url, max_attempts=3, aggressive_compress=True, spoiler=False)
            
            if file and fname:
                log.info(f"[PICK_MEDIA_SFW] Compression succeeded!")
                return (image_url, md5, site, file, fname, FetchError.NONE)
            
            # If compression failed for video, fall back to URL
            if is_video_url(image_url):
                log.info(f"[PICK_MEDIA_SFW] Video compression failed, falling back to URL")
                return (image_url, md5, site, None, None, FetchError.NONE)
            
            log.warning(f"[PICK_MEDIA_SFW] Compression failed, trying different image")
            last_error = FetchError.FILE_TOO_LARGE
        
        else:
            log.warning(f"[PICK_MEDIA_SFW] Unknown error: {process_error}, trying different image")
            last_error = FetchError.PROCESSING_FAILED
        
        # Mark this image as seen so we don't retry it
        if md5:
            seen.add(md5)

        # Check timeout again before retrying
        if time.time() - start_time > 720:
            log.warning("[PICK_MEDIA_SFW] Time limit reached after processing, falling back to URL")
            return (image_url, md5, site, None, None, FetchError.NONE)

    # Exhausted all tries
    log.warning(f"[PICK_MEDIA_SFW] Exhausted {tries} attempts, last error: {last_error.value}")
    return (None, None, None, None, None, last_error)


async def pick_image_sfw(tags: str | list[str], interaction_seen: InteractionSeen, category: Optional[str] = None) -> tuple[tuple[str | list[str], str | None, str] | None, FetchError]:
    """
    SFW version of pick_image - uses all booru sites.
    Tags should include rating:safe for SFW filtering.
    
    Returns: (picked, error) where picked is (url_or_urls, md5, site)
    - For preselected multi-image: url_or_urls is list[str]
    - For booru/single image: url_or_urls is str
    """
    md5s_in_memory = getattr(interaction_seen, "md5s", None)
    avoid = set(md5s_in_memory) if md5s_in_memory is not None else set(interaction_seen or [])

    # If InteractionSeen carries pair context, pull the pair's rolling md5 list
    actor_id = getattr(interaction_seen, "actor_id", None)
    target_id = getattr(interaction_seen, "target_id", None)
    if isinstance(actor_id, int) and isinstance(target_id, int):
        try:
            pair_md5s = await STATS_DB.load_pair_seen(actor_id, target_id)
            avoid |= set(pair_md5s)
        except Exception:
            pass

    tag_list = [tags] if isinstance(tags, str) else list(tags)
    all_seen_count = 0

    # 1. Try Pre-selected first (if category provided)
    if category:
        pre_res = fetch_preselected(category, avoid)
        if pre_res:
            # Found preselected image(s)! pre_res is (urls_list, md5, site)
            urls_list, md5, site = pre_res
            # Persist "seen" per pair
            if isinstance(actor_id, int) and isinstance(target_id, int):
                try:
                    await STATS_DB.add_pair_seen(actor_id, target_id, md5, site=site, max_entries=1000)
                except Exception:
                    pass
            # Return list of URLs for multi-image, or single URL for single
            if len(urls_list) == 1:
                return ((urls_list[0], md5, site), FetchError.NONE)
            else:
                return ((urls_list, md5, site), FetchError.NONE)

    for tag_query in tag_list:
        picked = None
        for _ in range(DEDUP_PULL_TRIES):
            res = await fetch_image(tag_query, avoid)  # Uses all sites (Gelbooru -> Rule34 -> Safebooru -> etc.)
            if not res:
                break
            url, md5, site = res
            if md5 and md5 in avoid:
                all_seen_count += 1
                continue
            picked = (url, md5, site)
            break

        if picked and picked[1]:
            # Persist "seen" per pair
            if isinstance(actor_id, int) and isinstance(target_id, int):
                try:
                    await STATS_DB.add_pair_seen(actor_id, target_id, picked[1], site=picked[2], max_entries=1000)
                except Exception:
                    pass
            return (picked, FetchError.NONE)
        if picked:
            return (picked, FetchError.NONE)

    # Determine specific error reason
    if all_seen_count > 0:
        return (None, FetchError.ALL_SEEN)
    return (None, FetchError.NO_RESULTS)

