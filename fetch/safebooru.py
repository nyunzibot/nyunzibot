import random
import asyncio
import aiohttp
import logging
import xml.etree.ElementTree as ET

from config import USER_AGENT
from .common import is_supported_file_url, size_ok, get_cached_count, set_cached_count

log = logging.getLogger("nyunzi")

# =========================
# SAFEBOORU FETCH (XML -> JSON/Construct)
# Strategy: Probe Count (XML) -> Random PID (JSON)
# =========================
async def fetch_image_safebooru(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    backoffs = [0.0, 1.0, 2.5, 5.0]

    LIMIT = 1
    MAX_ATTEMPTS = 5
    PID_HARD_CAP = 200_000

    # Strip rating:safe from tags - Safebooru is already SFW-only
    tags = " ".join(t for t in tags.split() if not t.lower().startswith("rating:"))

    # Score tiers (Safebooru scores are low)
    SCORE_TIERS: list[int | None] = [100, 50, 20, 10, None]

    def with_score_filter(base_tags: str, min_score: int | None) -> str:
        t = base_tags.strip()
        if min_score is None:
            return t
        return f"{t} score:>={min_score}".strip()

    def extract_count_from_root(root: ET.Element) -> int | None:
        try:
            c = int(root.attrib.get("count", "0"))
            return c if c > 0 else None
        except Exception:
            return None

    # Base URL for Safebooru DAPI
    BASE_URL = "https://safebooru.org/index.php?page=dapi&s=post&q=index"

    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        for tier in SCORE_TIERS:
            tier_tags = with_score_filter(tags, tier)
            tier_label = f">={tier}" if tier is not None else "none"

            # ---- Step 1: probe count (pid=0) for this tier ----
            count = get_cached_count("safebooru", tier_tags, tier_label)
            tier_pid_cap = PID_HARD_CAP

            if count is None:
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    params_probe = {
                        "limit": LIMIT,
                        "pid": 0,
                        "tags": tier_tags,
                    }

                    try:
                        async with session.get(
                            BASE_URL,
                            params=params_probe,
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as resp:
                            log.debug("[SAFE FETCH] tier=%s count_probe attempt=%s/%s status=%s",
                                     tier_label, attempt, MAX_ATTEMPTS, resp.status)
                            log.info("[SAFE FETCH] url=%s", resp.url)
                            
                            if resp.status == 429:
                                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                                continue
                            if resp.status != 200:
                                log.info("[SAFE PROBE] tier=%s status=%s (Retrying)", tier_label, resp.status)
                                continue

                            xml_text = await resp.text()
                            root = ET.fromstring(xml_text)
                            c = extract_count_from_root(root)
                            if c:
                                count = c
                                tier_pid_cap = min(tier_pid_cap, count - 1)
                                set_cached_count("safebooru", tier_tags, tier_label, c)
                                log.info("[SAFE PROBE] tier=%s status=%s count=%s", tier_label, resp.status, c)
                            else:
                                log.info("[SAFE PROBE] tier=%s status=%s count=None", tier_label, resp.status)
                            break
                    except Exception as e:
                        log.warning("[SAFE PROBE] probe error: %s", e)
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
            else:
                if count:
                    tier_pid_cap = min(tier_pid_cap, count - 1)

            if not count:
                log.info("[SAFE FETCH] tier=%s no count; trying next tier", tier_label)
                continue

            max_pid = min(count - 1, tier_pid_cap)
            if max_pid < 0:
                continue

            # ---- Step 2: fetch random pid ----
            for attempt in range(1, MAX_ATTEMPTS + 1):
                pid = random.randint(0, max_pid)
                params_fetch = {
                    "limit": LIMIT,
                    "pid": pid,
                    "tags": tier_tags,
                    "json": 1,
                }

                try:
                    async with session.get(
                        BASE_URL,
                        params=params_fetch,
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        if resp.status != 200:
                            continue
                        
                        data = await resp.json(content_type=None)
                        if not isinstance(data, list) or not data:
                            continue
                        
                        p = data[0]
                        url = p.get("file_url")
                        if not url:
                            directory = p.get("directory")
                            image = p.get("image")
                            if directory and image:
                                url = f"https://safebooru.org/images/{directory}/{image}"
                        
                        if not url or not is_supported_file_url(url):
                            continue

                        md5 = p.get("hash")
                        w = p.get("width")
                        h = p.get("height")
                        
                        if not size_ok(w, h):
                            continue
                        if md5 and md5 in avoid_md5s:
                            continue
                        
                        return (url, md5, "safebooru")
                except Exception as e:
                    log.warning("[SAFE FETCH] fetch error: %s", e)
                    continue

    return None
