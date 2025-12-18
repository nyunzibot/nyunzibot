import random
import asyncio
import aiohttp
import logging

from config import GELBOORU_API, GELBOORU_API_KEY, GELBOORU_USER_ID, USER_AGENT, SCORE_TIERS, LIMIT_TIERS, PAGES_PER_LIMIT
from .common import should_lower_limit, is_supported_file_url, size_ok, pid_max_for

log = logging.getLogger("nyunzi")

# =========================
# GELBOORU FETCH (JSON) -> (url, md5, site)
# =========================
async def fetch_image_gelbooru_01(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    if not (GELBOORU_API_KEY and GELBOORU_USER_ID):
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]

    for score_tag in SCORE_TIERS:
        tier_label = score_tag or "no-score"
        full_tags = f"{tags} {score_tag}".strip()
        pid_max = pid_max_for("gelbooru", score_tag)

        for limit in LIMIT_TIERS:
            for _ in range(PAGES_PER_LIMIT):
                http_status = None
                exc: Exception | None = None
                parse_failed = False
                data = None

                params = {
                    "limit": limit,
                    "tags": full_tags,
                    "api_key": GELBOORU_API_KEY,
                    "user_id": GELBOORU_USER_ID,
                }

                try:
                    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
                        async with session.get(
                            GELBOORU_API,
                            params=params,
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as resp:
                            http_status = resp.status
                            log.info("[GEL FETCH] tier=%s limit=%s pid<=%s status=%s", tier_label, limit, pid_max, http_status)
                            log.info("[GEL FETCH] url=%s", resp.url)

                            if http_status == 429:
                                await asyncio.sleep(backoffs[1])
                                break
                            if http_status != 200:
                                break

                            data = await resp.json(content_type=None)

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    exc = e
                except Exception as e:
                    exc = e
                    parse_failed = True

                if should_lower_limit(http_status, exc, parse_failed):
                    if http_status == 429:
                        await asyncio.sleep(backoffs[2])
                    break

                posts = None
                if isinstance(data, dict):
                    posts = data.get("post")
                elif isinstance(data, list):
                    posts = data

                if not posts:
                    continue
                if isinstance(posts, dict):
                    posts = [posts]

                random.shuffle(posts)
                for p in posts:
                    if not isinstance(p, dict):
                        continue
                    url = p.get("file_url")
                    md5 = p.get("md5")
                    if not url:
                        continue
                    if not is_supported_file_url(url):
                        continue
                    w = p.get("width")
                    h = p.get("height")
                    try:
                        w_i = int(w) if w is not None else None
                        h_i = int(h) if h is not None else None
                    except Exception:
                        w_i = None
                        h_i = None
                    if not size_ok(w_i, h_i):
                        continue
                    if md5 and md5 in avoid_md5s:
                        continue
                    return (url, md5, "gelbooru")

        log.info("[GEL FETCH] tier=%s lowering score tier -> next", tier_label)

    return None


# =========================
# GELBOORU FETCH (JSON) -> (url, md5, site)
# NO PID, NO SCORE TIERS, NO LIMIT TIERS
# =========================
async def fetch_image_gelbooru_02(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    if not (GELBOORU_API_KEY and GELBOORU_USER_ID):
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]

    LIMIT = 1000           # fixed request size
    MAX_ATTEMPTS = 5     # total requests per call (hard cap)

    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            http_status: int | None = None
            exc: Exception | None = None
            parse_failed = False
            data = None

            params = {
                "limit": LIMIT,
                "tags": tags.strip(),
                "api_key": GELBOORU_API_KEY,
                "user_id": GELBOORU_USER_ID,
                "json": 1,
            }

            try:
                async with session.get(
                    GELBOORU_API,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    http_status = resp.status
                    log.info(
                        "[GEL FETCH] attempt=%s/%s limit=%s status=%s",
                        attempt,
                        MAX_ATTEMPTS,
                        LIMIT,
                        http_status,
                    )
                    log.info("[GEL FETCH] url=%s", resp.url)

                    if http_status == 429:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
                    if http_status != 200:
                        continue

                    data = await resp.json(content_type=None)

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                exc = e
            except Exception as e:
                exc = e
                parse_failed = True

            if should_lower_limit(http_status, exc, parse_failed):
                if http_status == 429:
                    await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue

            posts = None
            if isinstance(data, dict):
                posts = data.get("post")
            elif isinstance(data, list):
                posts = data

            if not posts:
                continue
            if isinstance(posts, dict):
                posts = [posts]

            random.shuffle(posts)

            for p in posts:
                if not isinstance(p, dict):
                    continue

                url = p.get("file_url")
                md5 = p.get("md5")
                if not url:
                    continue
                if not is_supported_file_url(url):
                    continue

                w = p.get("width")
                h = p.get("height")
                try:
                    w_i = int(w) if w is not None else None
                    h_i = int(h) if h is not None else None
                except Exception:
                    w_i = None
                    h_i = None

                if not size_ok(w_i, h_i):
                    continue
                if md5 and md5 in avoid_md5s:
                    continue

                # ✅ Resolve immediately
                return (url, md5, "gelbooru")

    return None


# =========================
# GELBOORU FETCH (JSON) -> (url, md5, site)
# limit=1, pid random in [0, count-1]
# =========================
async def fetch_image_gelbooru(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    if not (GELBOORU_API_KEY and GELBOORU_USER_ID):
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]

    LIMIT = 1
    MAX_ATTEMPTS = 5
    # Hard safety clamp so you don't accidentally blast huge pid values forever
    PID_HARD_CAP = 10_000

    def extract_attrs_count(data) -> int | None:
        if not isinstance(data, dict):
            return None
        attrs = data.get("@attributes")
        if not isinstance(attrs, dict):
            return None
        try:
            c = int(attrs.get("count", 0))
            return c if c > 0 else None
        except Exception:
            return None

    def extract_single_post(data) -> dict | None:
        if not isinstance(data, dict):
            return None
        posts = data.get("post")
        if isinstance(posts, list) and posts:
            return posts[0] if isinstance(posts[0], dict) else None
        if isinstance(posts, dict):
            return posts
        return None

    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        # ---- Step 1: probe count ----
        count = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            params_probe = {
                "limit": LIMIT,
                "pid": 0,
                "tags": tags.strip(),
                "api_key": GELBOORU_API_KEY,
                "user_id": GELBOORU_USER_ID,
                "json": 1,
            }

            try:
                async with session.get(
                    GELBOORU_API,
                    params=params_probe,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    log.info("[GEL FETCH] count_probe attempt=%s/%s limit=%s pid=%s status=%s",
                             attempt, MAX_ATTEMPTS, LIMIT, 0, resp.status)
                    log.info("[GEL FETCH] url=%s", resp.url)

                    if resp.status == 429:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
                    if resp.status != 200:
                        continue

                    data_probe = await resp.json(content_type=None)
                    count = extract_attrs_count(data_probe)
                    PID_HARD_CAP = count - 1
                    break

            except (aiohttp.ClientError, asyncio.TimeoutError):
                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue
            except Exception:
                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue

        if not count:
            log.info("[GEL FETCH] no count available; cannot do pid-in-[0,count) strategy")
            return None

        # ---- Step 2: choose pid (basically “index”) ----
        max_pid = min(count - 1, PID_HARD_CAP)
        if max_pid <= 0:
            return None

        # We'll try a few random pid picks in case we hit a dead/filtered entry
        for attempt in range(1, MAX_ATTEMPTS + 1):
            pid = random.randint(0, max_pid)

            params = {
                "limit": LIMIT,
                "pid": pid,
                "tags": tags.strip(),
                "api_key": GELBOORU_API_KEY,
                "user_id": GELBOORU_USER_ID,
                "json": 1,
            }

            try:
                async with session.get(
                    GELBOORU_API,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    log.info("[GEL FETCH] attempt=%s/%s limit=%s pid=%s status=%s",
                             attempt, MAX_ATTEMPTS, LIMIT, pid, resp.status)
                    log.info("[GEL FETCH] url=%s", resp.url)

                    if resp.status == 429:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
                    if resp.status != 200:
                        continue

                    data = await resp.json(content_type=None)

            except (aiohttp.ClientError, asyncio.TimeoutError):
                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue
            except Exception:
                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue

            p = extract_single_post(data)
            if not p:
                continue

            url = p.get("file_url")
            md5 = p.get("md5")
            if not url or not is_supported_file_url(url):
                continue

            try:
                w_i = int(p.get("width")) if p.get("width") is not None else None
                h_i = int(p.get("height")) if p.get("height") is not None else None
            except Exception:
                w_i = None
                h_i = None

            if not size_ok(w_i, h_i):
                continue
            if md5 and md5 in avoid_md5s:
                continue

            return (url, md5, "gelbooru")

    return None