from config import DEDUP_PULL_TRIES
from .fetch_image import fetch_image
from db.stats import InteractionSeen
from db.runtime import STATS_DB
# Put this near pick_image in fetch/pick.py
from images.process import process_image  # make sure this import exists

async def pick_media(tags, seen, *, tries: int = 8):
    """
    Returns: (image_url, md5, site, file, fname) or None

    Behavior:
    - If the chosen post is a video AND process_image returns (None, None)
      (too large to attach / skipped), then we SKIP and retry another post.
    - Otherwise we return what we got.
    """
    for _ in range(tries):
        picked = await pick_image(tags, seen)
        if not picked:
            return None

        image_url, md5, site = picked
        file, fname = await process_image(image_url, max_attempts=3)

        # ✅ If it's a video and we couldn't attach it, skip and retry
        if _is_video_url(image_url) and (not file or not fname):
            if md5:
                seen.add(md5)
            continue

        return (image_url, md5, site, file, fname)

    return None


def _is_video_url(url: str) -> bool:
    u = (url or "").lower().split("?")[0].split("#")[0]
    return u.endswith((".mp4", ".webm"))


# =========================
# PICK IMAGE: dynamic tags + dedup (interaction + persistent)
# =========================
async def pick_image(tags: str | list[str], interaction_seen: InteractionSeen) -> tuple[str, str | None, str] | None:
    recent_seen = await STATS_DB.load_recent_seen(max_age_days=30)
    avoid = set(recent_seen) | set(interaction_seen.md5s)

    tag_list = [tags] if isinstance(tags, str) else list(tags)

    for tag_query in tag_list:
        picked = None
        for _ in range(DEDUP_PULL_TRIES):
            res = await fetch_image(tag_query, avoid)
            if not res:
                break
            url, md5, site = res
            if md5 and md5 in avoid:
                continue
            picked = (url, md5, site)
            break

        if picked and picked[1]:
            await STATS_DB.mark_seen(picked[1], picked[2])
            return picked
        if picked:
            return picked

    return None
