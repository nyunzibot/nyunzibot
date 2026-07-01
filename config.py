# =========================
# SECRETS (USE ENV VARS IN RAILWAY)
# Railway Variables (recommended):
# TOKEN
# RULE34_API_KEY
# RULE34_USER_ID
# GELBOORU_API_KEY
# GELBOORU_USER_ID
# DB_PATH (optional)
# =========================

import os

# NOTE: Keeping the same literal values as your original single-file bot,
# so behavior is unchanged when you run this refactor.
TOKEN = os.getenv("TOKEN", "")

# APIs
USER_AGENT = "nyunzi-bot/1.0"

# Rule34 (XML)
RULE34_API = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index"
RULE34_API_KEY = os.getenv("RULE34_API_KEY", "")
RULE34_USER_ID = os.getenv("RULE34_USER_ID", "")

# Rule34.us (Scraping)
RULE34US_URL = "https://rule34.us"

# Rule34Video (Scraping)
RULE34VIDEO_URL = "https://rule34video.com"

# Gelbooru (JSON for fetch, XML for count-probe)
GELBOORU_API = "https://gelbooru.com/index.php?page=dapi&s=post&q=index" # &json=1 for fetch
# GELBOORU_API_KEY = os.getenv("GELBOORU_API_KEY", "")
# GELBOORU_USER_ID = os.getenv("GELBOORU_USER_ID", "")
GELBOORU_API_KEY = os.getenv("GELBOORU_API_KEY", "")
GELBOORU_USER_ID = os.getenv("GELBOORU_USER_ID", "")

# Safebooru (XML for count, JSON for fetch)
SAFEBOORU_API = "https://safebooru.org/index.php?page=dapi&s=post&q=index"

# Konachan (Moebooru)
KONACHAN_API = "https://konachan.com/post"
KONACHAN_API_KEY = os.getenv("KONACHAN_API_KEY", "")
KONACHAN_LOGIN_ID = os.getenv("KONACHAN_LOGIN_ID", "")

# Yande.re (Moebooru)
YANDERE_API = "https://yande.re/post"
YANDERE_LOGIN_ID = ""
YANDERE_API_KEY = ""

# Danbooru
DANBOORU_API = "https://danbooru.donmai.us"
DANBOORU_API_KEY = os.getenv("DANBOORU_API_KEY", "")
DANBOORU_LOGIN_ID = os.getenv("DANBOORU_LOGIN_ID", "")

# Pixiv (requires refresh token - see https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362)
PIXIV_REFRESH_TOKEN = os.getenv("PIXIV_REFRESH_TOKEN", "")

# Persistent DB path (Railway Volume)
DB_PATH = "/data/stats.sqlite3"

# =========================
# SCORE + LIMIT BACKOFF
# =========================
SCORE_TIERS = [
    "score:>50",
    "score:>40",
    "score:>30",
    "score:>20",
    "",  # final fallback: no score filter
]

LIMIT_TIERS = [100, 50]
PAGES_PER_LIMIT = 1
DEDUP_PULL_TRIES = 6

# =========================
# SITE TOGGLES (Testing)
# =========================
ENABLE_GELBOORU = True
ENABLE_RULE34 = True
ENABLE_RULE34US = True
ENABLE_RULE34VIDEO = False
ENABLE_SAFEBOORU = True
ENABLE_KONACHAN = True
ENABLE_YANDERE = True
ENABLE_DANBOORU = True
ENABLE_PIXIV = True
ENABLE_NSFW_DETECTOR = False
