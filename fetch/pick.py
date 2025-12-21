from enum import Enum
import logging
from config import DEDUP_PULL_TRIES
from .fetch_image import fetch_image
from db.stats import InteractionSeen
from db.runtime import STATS_DB
from images.process import process_image, ProcessError

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
        FetchError.ALL_APIS_FAILED: "All image sources failed. Try again later 🔄",
    }
    return messages.get(error, "Something went wrong 😭 Try again.")


async def pick_media(tags, seen, *, tries: int = 8):
    """
    Returns: (image_url, md5, site, file, fname, error) tuple
    
    On success: (url, md5, site, file, fname, FetchError.NONE)
    On failure: (None, None, None, None, None, FetchError.<reason>)

    Smart Retry Behavior:
    - DOWNLOAD_FAILED: Retry download again, then try different image
    - FILE_TOO_LARGE: Try compression, then try different image
    - PROCESSING_FAILED: Retry processing, then try different image  
    - VIDEO_TOO_LARGE: Try different image (can't easily compress videos)
    - RATE_LIMITED: Return immediately (waiting is required)
    """
    last_error = FetchError.ALL_APIS_FAILED
    
    for attempt in range(tries):
        picked, fetch_error = await pick_image(tags, seen)
        if not picked:
            last_error = fetch_error
            log.warning(f"[PICK_MEDIA] No image picked on attempt {attempt+1}/{tries}: {fetch_error.value}")
            return (None, None, None, None, None, last_error)

        image_url, md5, site = picked
        log.info(f"[PICK_MEDIA] Attempt {attempt+1}/{tries}: Picked image from {site}")
        
        # First attempt at processing
        file, fname, process_error = await process_image(image_url, max_attempts=3)

        # If first attempt succeeded, we're done!
        if file and fname:
            log.info(f"[PICK_MEDIA] Success on attempt {attempt+1}/{tries}")
            return (image_url, md5, site, file, fname, FetchError.NONE)
        
        # ─── Handle specific errors with smart retries ───
        
        # RATE_LIMITED: Can't help by retrying
        if process_error == ProcessError.RATE_LIMITED:
            log.warning(f"[PICK_MEDIA] Rate limited, cannot retry")
            return (None, None, None, None, None, FetchError.RATE_LIMITED)
        
        # DOWNLOAD_FAILED: Try downloading again once more
        if process_error == ProcessError.DOWNLOAD_FAILED:
            log.info(f"[PICK_MEDIA] Download failed, retrying download...")
            file, fname, process_error = await process_image(image_url, max_attempts=5)
            if file and fname:
                log.info(f"[PICK_MEDIA] Download retry succeeded!")
                return (image_url, md5, site, file, fname, FetchError.NONE)
            log.warning(f"[PICK_MEDIA] Download retry also failed, trying different image")
            last_error = FetchError.DOWNLOAD_FAILED
        
        # PROCESSING_FAILED: Try processing again once more
        elif process_error == ProcessError.PROCESSING_FAILED:
            log.info(f"[PICK_MEDIA] Processing failed, retrying with compression...")
            # process_image now auto-tries compression on failure
            file, fname, process_error = await process_image(image_url, max_attempts=3, aggressive_compress=True)
            if file and fname:
                log.info(f"[PICK_MEDIA] Processing retry with compression succeeded!")
                return (image_url, md5, site, file, fname, FetchError.NONE)
            log.warning(f"[PICK_MEDIA] Processing retry also failed, trying different image")
            last_error = FetchError.PROCESSING_FAILED
        
        # FILE_TOO_LARGE: Try compression for images, skip videos
        elif process_error == ProcessError.FILE_TOO_LARGE:
            is_video = _is_video_url(image_url)
            if is_video:
                log.warning(f"[PICK_MEDIA] Video too large ({image_url[:50]}...), trying different image")
                last_error = FetchError.VIDEO_TOO_LARGE
            else:
                log.info(f"[PICK_MEDIA] File too large, trying compression...")
                file, fname, process_error = await process_image(image_url, max_attempts=3, aggressive_compress=True)
                if file and fname:
                    log.info(f"[PICK_MEDIA] Compression succeeded!")
                    return (image_url, md5, site, file, fname, FetchError.NONE)
                log.warning(f"[PICK_MEDIA] Compression failed, trying different image")
                last_error = FetchError.FILE_TOO_LARGE
        
        else:
            # Unknown error
            log.warning(f"[PICK_MEDIA] Unknown error: {process_error}, trying different image")
            last_error = FetchError.PROCESSING_FAILED
        
        # Mark this image as seen so we don't retry it
        if md5:
            seen.add(md5)

    # Exhausted all tries
    log.warning(f"[PICK_MEDIA] Exhausted {tries} attempts, last error: {last_error.value}")
    return (None, None, None, None, None, last_error)


def _is_video_url(url: str) -> bool:
    u = (url or "").lower().split("?")[0].split("#")[0]
    return u.endswith((".mp4", ".webm"))


# =========================
# PICK IMAGE: dynamic tags + dedup (interaction + persistent)
# =========================
async def pick_image(tags: str | list[str], interaction_seen: InteractionSeen) -> tuple[tuple[str, str | None, str] | None, FetchError]:
    # Persistent dedup is per unordered user-pair (Firestore pair_seen), not global.
    # We keep per-interaction dedup in memory via InteractionSeen.md5s.
    md5s_in_memory = getattr(interaction_seen, "md5s", None)
    avoid = set(md5s_in_memory) if md5s_in_memory is not None else set(interaction_seen or [])

    # If InteractionSeen carries pair context, pull the pair's rolling md5 list.
    actor_id = getattr(interaction_seen, "actor_id", None)
    target_id = getattr(interaction_seen, "target_id", None)
    if isinstance(actor_id, int) and isinstance(target_id, int):
        try:
            pair_md5s = await STATS_DB.load_pair_seen(actor_id, target_id)
            avoid |= set(pair_md5s)
        except Exception:
            # If Firestore is unavailable for any reason, we still run with in-memory dedup.
            pass

    tag_list = [tags] if isinstance(tags, str) else list(tags)
    all_seen_count = 0

    for tag_query in tag_list:
        picked = None
        for _ in range(DEDUP_PULL_TRIES):
            res = await fetch_image(tag_query, avoid)
            if not res:
                break
            url, md5, site = res
            if md5 and md5 in avoid:
                all_seen_count += 1
                continue
            picked = (url, md5, site)
            break

        if picked and picked[1]:
            # Persist "seen" per pair (rolling max 1000, oldest dropped).
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

