from config import DEDUP_PULL_TRIES
from .fetch_image import fetch_image
from db.stats import InteractionSeen
from db.runtime import STATS_DB

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
