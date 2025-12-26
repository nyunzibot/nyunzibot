"""
Safebooru-only pick module for SFW commands.
This module provides image fetching exclusively from Safebooru.
"""

from enum import Enum
import logging
from typing import Callable, Awaitable, Optional
from config import DEDUP_PULL_TRIES
from .safebooru import fetch_image_safebooru
from db.stats import InteractionSeen
from db.runtime import STATS_DB
from images.process import process_image, ProcessError
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
        FetchError.NO_RESULTS: "No matching images found for those tags 🔍",
        FetchError.ALL_SEEN: "You've seen all the images! Try different tags 🎲",
        FetchError.DOWNLOAD_FAILED: "Couldn't download the image (server issue) 🌐",
        FetchError.RATE_LIMITED: "API rate limit hit. Wait a moment and try again ⏳",
        FetchError.FILE_TOO_LARGE: "Image was too large for Discord (>25MB) 📦",
        FetchError.PROCESSING_FAILED: "Couldn't process the image 🖼️",
        FetchError.VIDEO_TOO_LARGE: "Video was too large to attach (>25MB) 🎬",
        FetchError.ALL_APIS_FAILED: "Safebooru couldn't find any matching images. Try different tags 🔄",
    }
    return messages.get(error, "Something went wrong 😭 Try again.")


def is_video_url(url: str) -> bool:
    u = (url or "").lower().split("?")[0].split("#")[0]
    return u.endswith((".mp4", ".webm"))


async def pick_media_safebooru(tags, seen, *, tries: int = 8, status_cb: Optional[Callable[[str], Awaitable[None]]] = None):
    """
    Safebooru-only version of pick_media.
    Returns: (image_url, md5, site, file, fname, error) tuple
    
    On success: (url, md5, site, file, fname, FetchError.NONE)
    On failure: (None, None, None, None, None, FetchError.<reason>)
    """
    start_time = time.time()
    last_error = FetchError.ALL_APIS_FAILED
    
    for attempt in range(tries):
        # Check overall timeout (12 minutes) to prevent Discord 401 (15 min limit)
        if time.time() - start_time > 720: 
            log.warning(f"[PICK_MEDIA_SAFE] Time limit reached ({int(time.time() - start_time)}s), stopping retries")
            if 'image_url' in locals() and image_url:
                 log.info(f"[PICK_MEDIA_SAFE] Falling back to URL due to timeout")
                 return (image_url, md5, site, None, None, FetchError.NONE)
            break

        picked, fetch_error = await pick_image_safebooru(tags, seen)
        if not picked:
            last_error = fetch_error
            log.warning(f"[PICK_MEDIA_SAFE] No image picked on attempt {attempt+1}/{tries}: {fetch_error.value}")
            return (None, None, None, None, None, last_error)

        image_url, md5, site = picked
        log.info(f"[PICK_MEDIA_SAFE] Attempt {attempt+1}/{tries}: Picked image from {site}")
        
        # First attempt at processing
        file, fname, process_error = await process_image(image_url, max_attempts=3)

        # If first attempt succeeded, we're done!
        if file and fname:
            log.info(f"[PICK_MEDIA_SAFE] Success on attempt {attempt+1}/{tries}")
            return (image_url, md5, site, file, fname, FetchError.NONE)
        
        # Handle specific errors with smart retries
        if process_error == ProcessError.RATE_LIMITED:
            log.warning(f"[PICK_MEDIA_SAFE] Rate limited, cannot retry")
            return (None, None, None, None, None, FetchError.RATE_LIMITED)
        
        if process_error == ProcessError.DOWNLOAD_FAILED:
            log.info(f"[PICK_MEDIA_SAFE] Download failed, retrying download...")
            file, fname, process_error = await process_image(image_url, max_attempts=5)
            if file and fname:
                log.info(f"[PICK_MEDIA_SAFE] Download retry succeeded!")
                return (image_url, md5, site, file, fname, FetchError.NONE)
            log.warning(f"[PICK_MEDIA_SAFE] Download retry also failed, trying different image")
            last_error = FetchError.DOWNLOAD_FAILED
        
        elif process_error == ProcessError.PROCESSING_FAILED:
            log.info(f"[PICK_MEDIA_SAFE] Processing failed, retrying with compression...")
            file, fname, process_error = await process_image(image_url, max_attempts=3, aggressive_compress=True)
            if file and fname:
                log.info(f"[PICK_MEDIA_SAFE] Processing retry with compression succeeded!")
                return (image_url, md5, site, file, fname, FetchError.NONE)
            log.warning(f"[PICK_MEDIA_SAFE] Processing retry also failed, trying different image")
            last_error = FetchError.PROCESSING_FAILED
        
        elif process_error == ProcessError.FILE_TOO_LARGE:
            log.info(f"[PICK_MEDIA_SAFE] File too large, trying compression...")
            if status_cb:
                await status_cb("<a:loading:1453449271839031487> Compressing...")
            
            file, fname, process_error = await process_image(image_url, max_attempts=3, aggressive_compress=True)
            
            if file and fname:
                log.info(f"[PICK_MEDIA_SAFE] Compression succeeded!")
                return (image_url, md5, site, file, fname, FetchError.NONE)
            
            # If compression failed for video, fall back to URL
            if is_video_url(image_url):
                log.info(f"[PICK_MEDIA_SAFE] Video compression failed, falling back to URL")
                return (image_url, md5, site, None, None, FetchError.NONE)
            
            log.warning(f"[PICK_MEDIA_SAFE] Compression failed, trying different image")
            last_error = FetchError.FILE_TOO_LARGE
        
        else:
            log.warning(f"[PICK_MEDIA_SAFE] Unknown error: {process_error}, trying different image")
            last_error = FetchError.PROCESSING_FAILED
        
        # Mark this image as seen so we don't retry it
        if md5:
            seen.add(md5)

        # Check timeout again before retrying
        if time.time() - start_time > 720:
            log.warning("[PICK_MEDIA_SAFE] Time limit reached after processing, falling back to URL")
            return (image_url, md5, site, None, None, FetchError.NONE)

    # Exhausted all tries
    log.warning(f"[PICK_MEDIA_SAFE] Exhausted {tries} attempts, last error: {last_error.value}")
    return (None, None, None, None, None, last_error)


async def pick_image_safebooru(tags: str | list[str], interaction_seen: InteractionSeen) -> tuple[tuple[str, str | None, str] | None, FetchError]:
    """
    Safebooru-only version of pick_image.
    Uses only Safebooru as the image source.
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

    for tag_query in tag_list:
        picked = None
        for _ in range(DEDUP_PULL_TRIES):
            res = await fetch_image_safebooru(tag_query, avoid)
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
