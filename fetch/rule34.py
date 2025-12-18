import random
import asyncio
import aiohttp
import logging
import xml.etree.ElementTree as ET

from config import RULE34_API, RULE34_API_KEY, RULE34_USER_ID, USER_AGENT, SCORE_TIERS, LIMIT_TIERS, PAGES_PER_LIMIT
from .common import should_lower_limit, is_supported_file_url, size_ok, pid_max_for

log = logging.getLogger("nyunzi")

# =========================
# RULE34 FETCH (XML) -> (url, md5, site)
# =========================
async def fetch_image_rule34_01(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    if not (RULE34_API_KEY and RULE34_USER_ID):
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]

    for score_tag in SCORE_TIERS:
        tier_label = score_tag or "no-score"
        full_tags = f"{tags} {score_tag}".strip()
        pid_max = pid_max_for("rule34", score_tag)

        for limit in LIMIT_TIERS:
            for _ in range(PAGES_PER_LIMIT):
                http_status = None
                exc: Exception | None = None
                xml = None

                params = {
                    "limit": limit,
                    "pid": random.randint(0, pid_max),
                    "tags": full_tags,
                    "api_key": RULE34_API_KEY,
                    "user_id": RULE34_USER_ID,
                }

                try:
                    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
                        async with session.get(
                            RULE34_API,
                            params=params,
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as resp:
                            http_status = resp.status
                            log.info("[R34 FETCH] tier=%s limit=%s pid<=%s status=%s", tier_label, limit, pid_max, http_status)
                            log.info("[R34 FETCH] url=%s", resp.url)

                            if http_status == 429:
                                await asyncio.sleep(backoffs[1])
                                break
                            if http_status != 200:
                                break

                            xml = await resp.text()

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    exc = e

                if should_lower_limit(http_status, exc, parse_failed=False):
                    if http_status == 429:
                        await asyncio.sleep(backoffs[2])
                    break

                try:
                    root = ET.fromstring(xml or "")
                except ET.ParseError as e:
                    log.warning("[R34 FETCH] tier=%s limit=%s XML parse error: %s", tier_label, limit, e)
                    break

                posts = root.findall("post")
                if not posts:
                    continue

                random.shuffle(posts)
                for post in posts:
                    url = post.attrib.get("file_url")
                    md5 = post.attrib.get("md5")
                    if not url:
                        continue
                    if not is_supported_file_url(url):
                        continue
                    try:
                        w_i = int(post.attrib.get("width")) if post.attrib.get("width") else None
                        h_i = int(post.attrib.get("height")) if post.attrib.get("height") else None
                    except Exception:
                        w_i = None
                        h_i = None
                    if not size_ok(w_i, h_i):
                        continue
                    if md5 and md5 in avoid_md5s:
                        continue
                    return (url, md5, "rule34")

        log.info("[R34 FETCH] tier=%s lowering score tier -> next", tier_label)

    return None

# =========================
# RULE34 FETCH (XML) -> (url, md5, site)
# NO PID, NO SCORE TIERS, NO LIMIT TIERS
# =========================
async def fetch_image_rule34_02(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    if not (RULE34_API_KEY and RULE34_USER_ID):
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]

    LIMIT = 100          # fixed batch size
    MAX_ATTEMPTS = 5    # total requests per call (hard cap)

    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            http_status: int | None = None
            exc: Exception | None = None
            xml: str | None = None

            params = {
                "limit": LIMIT,
                "tags": tags.strip(),
                "api_key": RULE34_API_KEY,
                "user_id": RULE34_USER_ID,
            }

            try:
                async with session.get(
                    RULE34_API,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    http_status = resp.status
                    log.info("[R34 FETCH] attempt=%s/%s limit=%s status=%s", attempt, MAX_ATTEMPTS, LIMIT, http_status)
                    log.info("[R34 FETCH] url=%s", resp.url)

                    if http_status == 429:
                        # back off (slightly increasing)
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
                    if http_status != 200:
                        continue

                    xml = await resp.text()

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                exc = e

            if should_lower_limit(http_status, exc, parse_failed=False):
                if http_status == 429:
                    await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue

            try:
                root = ET.fromstring(xml or "")
            except ET.ParseError as e:
                log.warning("[R34 FETCH] XML parse error: %s", e)
                continue

            posts = root.findall("post")
            if not posts:
                continue

            random.shuffle(posts)

            for post in posts:
                url = post.attrib.get("file_url")
                md5 = post.attrib.get("md5")
                if not url:
                    continue
                if not is_supported_file_url(url):
                    continue

                try:
                    w_i = int(post.attrib.get("width")) if post.attrib.get("width") else None
                    h_i = int(post.attrib.get("height")) if post.attrib.get("height") else None
                except Exception:
                    w_i = None
                    h_i = None

                if not size_ok(w_i, h_i):
                    continue
                if md5 and md5 in avoid_md5s:
                    continue

                # ✅ resolve immediately
                return (url, md5, "rule34")

    return None


# =========================
# RULE34 FETCH (XML) -> (url, md5, site)
# limit=1, pid random in [0, count-1]
# =========================
async def fetch_image_rule34(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    if not (RULE34_API_KEY and RULE34_USER_ID):
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]

    LIMIT = 1
    MAX_ATTEMPTS = 5
    PID_HARD_CAP = 200_000  # safety clamp (optional, but recommended)

    def extract_count_from_root(root: ET.Element) -> int | None:
        # <posts count="135400" offset="777">
        try:
            c = int(root.attrib.get("count", "0"))
            return c if c > 0 else None
        except Exception:
            return None

    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        # ---- Step 1: probe count (pid=0) ----
        count: int | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            params_probe = {
                "limit": LIMIT,
                "pid": 0,
                "tags": tags.strip(),
                "api_key": RULE34_API_KEY,
                "user_id": RULE34_USER_ID,
            }

            try:
                async with session.get(
                    RULE34_API,
                    params=params_probe,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    log.info("[R34 FETCH] count_probe attempt=%s/%s limit=%s pid=%s status=%s",
                             attempt, MAX_ATTEMPTS, LIMIT, 0, resp.status)
                    log.info("[R34 FETCH] url=%s", resp.url)

                    if resp.status == 429:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
                    if resp.status != 200:
                        continue

                    xml0 = await resp.text()

                try:
                    root0 = ET.fromstring(xml0 or "")
                except ET.ParseError as e:
                    log.warning("[R34 FETCH] count_probe XML parse error: %s", e)
                    continue

                count = extract_count_from_root(root0)
                PID_HARD_CAP = count - 1
                break

            except (aiohttp.ClientError, asyncio.TimeoutError):
                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue
            except Exception:
                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue

        if not count:
            log.info("[R34 FETCH] no count available; cannot do pid-in-[0,count) strategy")
            return None

        max_pid = min(count - 1, PID_HARD_CAP)
        if max_pid <= 0:
            return None

        # ---- Step 2: fetch random pid pages (limit=1) ----
        for attempt in range(1, MAX_ATTEMPTS + 1):
            pid = random.randint(0, max_pid)

            params = {
                "limit": LIMIT,
                "pid": pid,
                "tags": tags.strip(),
                "api_key": RULE34_API_KEY,
                "user_id": RULE34_USER_ID,
            }

            try:
                async with session.get(
                    RULE34_API,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    log.info("[R34 FETCH] attempt=%s/%s limit=%s pid=%s status=%s",
                             attempt, MAX_ATTEMPTS, LIMIT, pid, resp.status)
                    log.info("[R34 FETCH] url=%s", resp.url)

                    if resp.status == 429:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
                    if resp.status != 200:
                        continue

                    xml = await resp.text()

            except (aiohttp.ClientError, asyncio.TimeoutError):
                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue
            except Exception:
                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue

            try:
                root = ET.fromstring(xml or "")
            except ET.ParseError as e:
                log.warning("[R34 FETCH] XML parse error: %s", e)
                continue

            post = root.find("post")
            if post is None:
                continue

            url = post.attrib.get("file_url")
            md5 = post.attrib.get("md5")
            if not url or not is_supported_file_url(url):
                continue

            try:
                w_i = int(post.attrib.get("width")) if post.attrib.get("width") else None
                h_i = int(post.attrib.get("height")) if post.attrib.get("height") else None
            except Exception:
                w_i = None
                h_i = None

            if not size_ok(w_i, h_i):
                continue
            if md5 and md5 in avoid_md5s:
                continue

            return (url, md5, "rule34")

    return None
