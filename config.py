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

# NOTE: Keeping the same literal values as your original single-file bot,
# so behavior is unchanged when you run this refactor.
TOKEN = "MTQ0OTg0MDM2Mzg3MDM1OTc2Mw.GJ_Y_k.Grssi02jlFr4J1T1Wrd1JI73xO17qTlEZLZUcg"

# APIs
USER_AGENT = "nyunzi-bot/1.0"

# Rule34 (XML)
RULE34_API = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index"
RULE34_API_KEY = "a8a50348e0754ddbee7de5e869427460b1e424c0109130d53d169bf0cb99c21827b2222c2c3c59352c7a1b847b0d1e869838aee87a59a2d2bddb6811bbbdcae8"
RULE34_USER_ID = "5699450"

# Rule34.us (Scraping)
RULE34US_URL = "https://rule34.us"

# Gelbooru (JSON for fetch, XML for count-probe)
GELBOORU_API = "https://gelbooru.com/index.php?page=dapi&s=post&q=index" # &json=1 for fetch
GELBOORU_API_KEY = "04176dbed5e2dcb5f047e9b684af9fac71df32281b10c92efff66da5dc97bd4710f78a81d87dd29d2670b97c6b1768f153902124648253b62fff50b85ea1049e"
GELBOORU_USER_ID = "1873378"

# Safebooru (XML for count, JSON for fetch)
SAFEBOORU_API = "https://safebooru.org/index.php?page=dapi&s=post&q=index"

# Konachan (Moebooru)
KONACHAN_API = "https://konachan.com/post"
KONACHAN_API_KEY = "jtVwWKhWbBLcCBV-iaNAxw"
KONACHAN_LOGIN_ID = "nyunzibot"

# Yande.re (Moebooru)
YANDERE_API = "https://yande.re/post"
YANDERE_LOGIN_ID = ""
YANDERE_API_KEY = ""

# Danbooru
DANBOORU_API = "https://danbooru.donmai.us"
DANBOORU_API_KEY = "rghpNgC2KboozqiixztXaXSJ"
DANBOORU_LOGIN_ID = "nyunzibot"

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
