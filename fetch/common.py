import time

def should_lower_limit(http_status: int | None, exc: Exception | None, parse_failed: bool) -> bool:
    if parse_failed:
        return True
    if exc is not None:
        return True
    if http_status in (429, 500, 502, 503, 504):
        return True
    if http_status in (400, 413, 414, 422):
        return True
    return False

def is_supported_file_url(url: str) -> bool:
    u = (url or "").lower()
    if not u.startswith("http"):
        return False

    # ✅ now allow images + gif + mp4/webm
    ok_ext = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm")
    return u.endswith(ok_ext)

def size_ok(width: int | None, height: int | None) -> bool:
    if width is None or height is None:
        return True
    if width < 700 or height < 700:
        return False
    if width > 9000 or height > 9000:
        return False
    return True

# =========================
# PID TUNING (BIGGER = fewer repeats)
# =========================
def pid_max_for(site: str, score_tag: str) -> int:
    # IMPORTANT: high score => fewer pages => repeats.
    # Widen pid substantially so each retry explores different pages (fewer total fetches needed).
    if site == "gelbooru":
        if score_tag == "score:>50": return 1
        if score_tag == "score:>40": return 2
        if score_tag == "score:>30": return 3
        if score_tag == "score:>20": return 4
        return 5
    else:  # rule34
        if score_tag == "score:>50": return 1
        if score_tag == "score:>40": return 2
        if score_tag == "score:>30": return 3
        if score_tag == "score:>20": return 4
        return 5

# =========================
# PROBE CACHE
# Simple in-memory cache: (site, tags, tier) -> (count, timestamp)
# TTL: 5 minutes? actually for this use case, even 30s is enough to survive the retry loop.
# Let's say 60 seconds to be safe.
# =========================
_PROBE_CACHE = {}

def get_cached_count(site: str, tags: str, tier: str) -> int | None:
    key = (site, tags, tier)
    entry = _PROBE_CACHE.get(key)
    if not entry:
        return None
    val, ts = entry
    if time.time() - ts > 60: # 60s TTL
        del _PROBE_CACHE[key]
        return None
    return val

def set_cached_count(site: str, tags: str, tier: str, count: int):
    key = (site, tags, tier)
    _PROBE_CACHE[key] = (count, time.time())
