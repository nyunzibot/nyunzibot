import random
import asyncio
import aiohttp
import logging

from config import DANBOORU_API, DANBOORU_API_KEY, DANBOORU_LOGIN_ID, USER_AGENT
from .common import is_supported_file_url, size_ok, get_cached_count, set_cached_count

log = logging.getLogger("nyunzi")

# =========================
# DANBOORU FETCH (JSON)
# Strategy: Probe Count (JSON) -> Random Page (JSON)
# =========================
async def fetch_image_danbooru(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    backoffs = [0.0, 1.0, 2.5, 5.0]

    LIMIT = 1
    MAX_ATTEMPTS = 5
    # Danbooru limits deep paging for free users (usually page <= 1000)
    PID_HARD_CAP = 1_000

    # Score tiers
    SCORE_TIERS: list[int | None] = [100, 50, 20, None]

    def with_score_filter(base_tags: str, min_score: int | None) -> str:
        t = base_tags.strip()
        if min_score is None:
            return t
        return f"{t} score:>={min_score}".strip()

    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        for tier in SCORE_TIERS:
            tier_tags = with_score_filter(tags, tier)
            tier_label = f">={tier}" if tier is not None else "none"

            # ---- Step 1: probe count ----
            # Danbooru count API: /counts/posts.json
            url_count = f"{DANBOORU_API}/counts/posts.json"
            count: int | None = None

            count = get_cached_count("danbooru", tier_tags, tier_label)

            if count is None:
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    try:
                        async with session.get(
                            url_count,
                            params={"tags": tier_tags},
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as resp:
                            log.info("[DAN FETCH] tier=%s count_probe attempt=%s/%s status=%s",
                                     tier_label, attempt, MAX_ATTEMPTS, resp.status)
                            log.info("[DAN FETCH] url=%s", resp.url)
                            
                            if resp.status == 200:
                                data = await resp.json()
                                # {"counts": {"posts": 123}}
                                count = data.get("counts", {}).get("posts")
                                if count is not None:
                                    set_cached_count("danbooru", tier_tags, tier_label, count)
                                break
                            elif resp.status == 422:
                                # Too complex
                                break
                            elif resp.status == 429:
                                 await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                    except Exception as e:
                        log.warning("[DAN FETCH] probe error: %s", e)
                        continue

            if not count:
                log.info("[DAN FETCH] tier=%s no count; trying next tier", tier_label)
                continue

            max_page = min(count, PID_HARD_CAP)
            if max_page < 1:
                continue

            # ---- Step 2: fetch random page ----
            url_posts = f"{DANBOORU_API}/posts.json"

            for attempt in range(1, MAX_ATTEMPTS + 1):
                page = random.randint(1, max_page)
                params_fetch = {
                    "limit": 1,
                    "page": page,
                    "tags": tier_tags,
                }

                try:
                    async with session.get(
                        url_posts,
                        params=params_fetch,
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        if resp.status != 200:
                            continue
                        
                        data = await resp.json()
                        if not isinstance(data, list) or not data:
                            continue
                        
                        p = data[0]
                        url = p.get("file_url") or p.get("large_file_url")
                        if not url or not is_supported_file_url(url):
                            continue

                        md5 = p.get("md5")
                        w = p.get("image_width")
                        h = p.get("image_height")
                        
                        if not size_ok(w, h):
                            continue
                        if md5 and md5 in avoid_md5s:
                            continue
                        
                        return (url, md5, "danbooru")
                except Exception as e:
                    log.warning("[DAN FETCH] fetch error: %s", e)
                    continue

    return None
