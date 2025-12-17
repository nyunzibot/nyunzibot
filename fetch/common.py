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
    for ext in (".webm", ".mp4", ".gif"):
        if u.endswith(ext):
            return False
    return True

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
