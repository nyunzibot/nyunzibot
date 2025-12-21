from enum import Enum
from config import DEDUP_PULL_TRIES
from .fetch_image import fetch_image
from db.stats import InteractionSeen
from db.runtime import STATS_DB
from images.process import process_image, ProcessError


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

    Behavior:
    - If the chosen post is a video AND process_image returns (None, None)
      (too large to attach / skipped), then we SKIP and retry another post.
    - Otherwise we return what we got.
    """
    last_error = FetchError.ALL_APIS_FAILED
    video_too_large_count = 0
    
    for _ in range(tries):
        picked, fetch_error = await pick_image(tags, seen)
        if not picked:
            last_error = fetch_error
            return (None, None, None, None, None, last_error)

        image_url, md5, site = picked
        file, fname, process_error = await process_image(image_url, max_attempts=3)

        # ✅ If it's a video and we couldn't attach it, skip and retry
        if _is_video_url(image_url) and (not file or not fname):
            if md5:
                seen.add(md5)
            video_too_large_count += 1
            last_error = FetchError.VIDEO_TOO_LARGE
            continue
        
        # Map process errors to fetch errors
        if not file or not fname:
            if process_error == ProcessError.RATE_LIMITED:
                last_error = FetchError.RATE_LIMITED
            elif process_error == ProcessError.FILE_TOO_LARGE:
                last_error = FetchError.FILE_TOO_LARGE
            elif process_error == ProcessError.DOWNLOAD_FAILED:
                last_error = FetchError.DOWNLOAD_FAILED
            elif process_error == ProcessError.PROCESSING_FAILED:
                last_error = FetchError.PROCESSING_FAILED
            else:
                last_error = FetchError.PROCESSING_FAILED
            return (None, None, None, None, None, last_error)

        return (image_url, md5, site, file, fname, FetchError.NONE)

    # If we exhausted tries, it was likely all videos too large
    if video_too_large_count > 0:
        last_error = FetchError.VIDEO_TOO_LARGE
    
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

