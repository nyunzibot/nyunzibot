import random
import asyncio
import aiohttp
import logging
import xml.etree.ElementTree as ET

from config import KONACHAN_API, USER_AGENT
from .common import is_supported_file_url, size_ok

log = logging.getLogger("nyunzi")

# =========================
# KONACHAN FETCH (XML -> JSON)
# Strategy: Probe Count (XML) -> Random PID (JSON)
# =========================
async def fetch_image_konachan(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    backoffs = [0.0, 1.0, 2.5, 5.0]

    LIMIT = 1
    MAX_ATTEMPTS = 5
    PID_HARD_CAP = 100_000

    # Score tiers
    SCORE_TIERS: list[int | None] = [500, 250, 100, 50, None]

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

    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        for tier in SCORE_TIERS:
            tier_tags = with_score_filter(tags, tier)
            tier_label = f">={tier}" if tier is not None else "none"

            # ---- Step 1: probe count (limit=1, page=1) for this tier ----
            count: int | None = None
            tier_pid_cap = PID_HARD_CAP

            # Moebooru XML endpoint: /post.xml
            url_xml = f"{KONACHAN_API}.xml"

            for attempt in range(1, MAX_ATTEMPTS + 1):
                params_probe = {
                    "limit": 1,
                    "tags": tier_tags,
                }

                try:
                    async with session.get(
                        url_xml,
                        params=params_probe,
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        log.info("[KONA FETCH] tier=%s count_probe attempt=%s/%s status=%s",
                                 tier_label, attempt, MAX_ATTEMPTS, resp.status)
                        
                        if resp.status == 429:
                            await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                            continue
                        if resp.status != 200:
                            continue

                        xml_text = await resp.text()
                        root = ET.fromstring(xml_text)
                        count = extract_count_from_root(root)
                        if count:
                            tier_pid_cap = min(tier_pid_cap, count)
                        break
                except Exception as e:
                    log.warning("[KONA FETCH] probe error: %s", e)
                    await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                    continue

            if not count:
                log.info("[KONA FETCH] tier=%s no count; trying next tier", tier_label)
                continue

            max_page = min(count, tier_pid_cap)
            if max_page < 1:
                continue

            # ---- Step 2: fetch random page (limit=1) ----
            # Moebooru JSON endpoint: /post.json
            url_json = f"{KONACHAN_API}.json"

            for attempt in range(1, MAX_ATTEMPTS + 1):
                # Moebooru 'page' is 1-indexed.
                page = random.randint(1, max_page)
                params_fetch = {
                    "limit": 1,
                    "page": page,
                    "tags": tier_tags,
                }

                try:
                    async with session.get(
                        url_json,
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
                        if not url or not is_supported_file_url(url):
                            continue

                        md5 = p.get("md5")
                        w = p.get("width")
                        h = p.get("height")
                        
                        if not size_ok(w, h):
                            continue
                        if md5 and md5 in avoid_md5s:
                            continue
                        
                        return (url, md5, "konachan")
                except Exception as e:
                    log.warning("[KONA FETCH] fetch error: %s", e)
                    continue

    return None
