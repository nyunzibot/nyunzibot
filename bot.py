import random
import aiohttp
import io
import logging
import os
import asyncio
import sqlite3
import time
import discord
import xml.etree.ElementTree as ET
from discord.ext import commands
from discord import app_commands
from PIL import Image

# =========================
# LOGGING (Railway-friendly)
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)
log = logging.getLogger("nyunzi")
log.info("Process boot ✅")

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
TOKEN = "MTQ0OTg0MDM2Mzg3MDM1OTc2Mw.GJ_Y_k.Grssi02jlFr4J1T1Wrd1JI73xO17qTlEZLZUcg"

# Rule34 (XML)
BOORU_API = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index"
RULE34_API_KEY = "a8a50348e0754ddbee7de5e869427460b1e424c0109130d53d169bf0cb99c21827b2222c2c3c59352c7a1b847b0d1e869838aee87a59a2d2bddb6811bbbdcae8"
RULE34_USER_ID = "5699450"

# Gelbooru JSON API endpoint
GELBOORU_API = "https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1"
GELBOORU_API_KEY = "04176dbed5e2dcb5f047e9b684af9fac71df32281b10c92efff66da5dc97bd4710f78a81d87dd29d2670b97c6b1768f153902124648253b62fff50b85ea1049e"
GELBOORU_USER_ID = "1873378"

# APIs
USER_AGENT = "nyunzi-bot/1.0"
RULE34_API = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index"  # XML
GELBOORU_API = "https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1"  # JSON

# Persistent DB path (Railway Volume)
DB_PATH = "/data/stats.sqlite3"

log.info("DB_PATH=%s", DB_PATH)
log.info("Rule34 enabled=%s", bool(RULE34_API_KEY and RULE34_USER_ID))
log.info("Gelbooru enabled=%s", bool(GELBOORU_API_KEY and GELBOORU_USER_ID))

if not TOKEN:
    log.warning("TOKEN missing! Bot cannot log in (set Railway variable TOKEN).")
if not (RULE34_API_KEY and RULE34_USER_ID):
    log.warning("RULE34_API_KEY or RULE34_USER_ID missing! Rule34 fetching will be skipped.")
if not (GELBOORU_API_KEY and GELBOORU_USER_ID):
    log.warning("GELBOORU_API_KEY or GELBOORU_USER_ID missing! Gelbooru fetching will be skipped.")

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
# TAGS
# - Base tags define the "action"
# - Positive sets rotate to improve quality/diversity
# - Negatives reduce bad content
#
# NOTE: Your “not explicit” request conflicts with adult booru tags.
# Keep/adjust these to what you want.
# =========================
NEGATIVE_TAGS = (
    "-video -gif "
    "-loli -shota -young -underage -child -minor -kid "
    "-furry -anthro -feral -animal -bestiality "
    "-rape -raped -nonconsensual -forced -dubious_consent "
    "-incest -family "
    "-gore -blood -death "
    "-scat -watersports -vomit -diaper "
    "-inflation -vore -oviposition -egg "
    "-pregnant -birth -lactation"
)

# Base tags (edit freely)
PLAP_BASE = "futa_on_female sex_from_behind"
SUCC_BASE = "futa_on_female oral"

# Rotate positives to avoid “same top few” posts
PLAP_POSITIVE_SETS = [
    "1girl 1futa"
]

SUCC_POSITIVE_SETS = [
    "1girl 1futa"
]

# Rotate artist/style boosts (optional quality)
ARTIST_BOOSTS = [
    "rikolo",
    "nyl2",
    "nyunnzi",
    "exga",
    "affect3d",
    "lewdua",
    "zer0",
    "afrobull",
    "bouquetman",
    "aanix",
    "grand_cupido",
]

def build_tags(base: str, positives: list[str]) -> str:
    # pick 1–2 positives to keep queries effective but not too strict
    k = 2 if len(positives) >= 2 else 1
    p = random.sample(positives, k=k)
    return f"{base} {' '.join(p)} {NEGATIVE_TAGS}".strip()

def build_tag_ladder(base: str, positives: list[str]) -> list[str]:
    """Tag fallback ladder:
    strict/high-quality -> relax step-by-step -> base only.
    Also optionally injects a rotating artist boost for quality.
    """
    artist = random.choice(ARTIST_BOOSTS) if ARTIST_BOOSTS else None

    quality_strict = []
    focus_strict = []

    k = 2 if len(positives) >= 2 else 1
    p = random.sample(positives, k=k)

    ladders: list[list[str]] = [
        [base, *p, *quality_strict, *focus_strict, artist],
        [base, *p, *quality_strict, artist],
        [base, *p, artist],
        [base, *p],
        [base],
    ]

    out: list[str] = []
    for parts in ladders:
        parts = [x for x in parts if x]
        out.append(f"{' '.join(parts)} {NEGATIVE_TAGS}".strip())
    return out

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# SAFE INTERACTION ACK (prevents 10062)
# IMPORTANT: call this as the FIRST awaited line in every command/callback
# =========================
async def safe_defer(interaction: discord.Interaction, *, thinking: bool = True) -> bool:
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=thinking)
        return True
    except discord.NotFound:
        log.warning("[DEFER] Unknown interaction (10062) – clicked too late or network hiccup")
        return False
    except Exception as e:
        log.warning("[DEFER] failed: %s: %s", type(e).__name__, e)
        return False

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
# LINES
# =========================
PLAP_LINES_INTIMATE_NATURAL = [
    "😶 {actor} plaps {target} and stays close, letting the moment linger.",
    "🔥 Without hesitation, {actor} plaps {target}, closing the distance.",
    "😳 {actor} plaps {target} with confidence, clearly aware of how close they are.",
    "👁️ After {actor} plaps {target}, neither of them moves right away.",
    "🫣 {actor} plaps {target} softly, but the intention is unmistakable.",
    "😈 {actor} plaps {target} and remains right there, unbothered by the tension.",
    "🔥 The way {actor} plaps {target} makes the closeness feel deliberate.",
    "😳 {actor} plaps {target}, lingering just long enough to make it personal.",
    "👀 Maintaining eye contact, {actor} plaps {target} without backing off.",
    "🖤 {actor} plaps {target}, the space between them suddenly very small.",
    "🔥 After {actor} plaps {target}, the playful energy shifts into something heavier.",
    "😶‍🌫️ {actor} plaps {target} and doesn’t pretend the moment is still casual.",
    "😈 Calm and certain, {actor} plaps {target} and stays close.",
    "😳 {actor} plaps {target}, both clearly aware of the tension now.",
    "🔥 The way {actor} plaps {target} leaves no room for misunderstanding.",
    "👁️ {actor} plaps {target}, letting the silence do the talking.",
    "🫶 With quiet confidence, {actor} plaps {target} and doesn’t pull away.",
    "😈 {actor} plaps {target}, fully owning how intimate it suddenly feels.",
    "🔥 {actor} plaps {target}, the closeness afterward very intentional.",
    "😳 After {actor} plaps {target}, neither rushes to break the moment.",
]

SUCC_LINES_INTIMATE = [
    "😳 {actor} succs {target}, slow at first, like they’re testing the reaction.",
    "🔥 {actor} succs {target} with zero hesitation, like this was inevitable.",
    "🫣 {actor} succs {target} and doesn’t break the moment when it gets quiet.",
    "😈 {actor} succs {target}, making it painfully clear who’s in control.",
    "👁️ {actor} succs {target} and holds eye contact like it’s a challenge.",
    "🖤 {actor} succs {target} and stays close afterward, unapologetic.",
    "😶‍🌫️ {actor} succs {target}, and the vibe shifts into something heavier.",
    "🫶 {actor} succs {target} with a calm confidence that’s hard to ignore.",
    "🔥 {actor} succs {target}, lingering just long enough to make it personal.",
    "😳 After {actor} succs {target}, neither of them rushes to reset the mood.",
]

def plap_summary(actor: discord.User, target: discord.User, count: int) -> str:
    time_word = "time" if count == 1 else "times"
    if count <= 1:
        pool = [
            f"{actor.mention} plapped {target.mention} {count} {time_word}!",
            f"{actor.mention} has plapped {target.mention} {count} {time_word}.",
        ]
    elif count <= 3:
        pool = [
            f"{actor.mention} has now plapped {target.mention} {count} {time_word}!",
            f"{actor.mention} keeps plapping {target.mention} — {count} {time_word} now!",
            f"{count} {time_word} in, and {actor.mention} isn’t stopping with {target.mention}.",
        ]
    elif count <= 6:
        pool = [
            f"{actor.mention} is on a roll — {count} {time_word} on {target.mention}!",
            f"{count} {time_word} now… {actor.mention} is clearly committed to {target.mention}.",
            f"{actor.mention} keeps coming back — {count} {time_word} and counting.",
        ]
    else:
        pool = [
            f"{count} {time_word}. Yeah. {actor.mention} is absolutely not done with {target.mention}.",
            f"{actor.mention} has lost count — but it’s at least {count} {time_word}.",
            f"{actor.mention} keeps plapping {target.mention}. Nobody’s pretending anymore ({count} {time_word}).",
        ]
    return random.choice(pool)

def succ_summary(actor: discord.User, target: discord.User, count: int) -> str:
    time_word = "time" if count == 1 else "times"
    if count <= 1:
        pool = [
            f"{actor.mention} succ’d {target.mention} {count} {time_word}!",
            f"{actor.mention} has succ’d {target.mention} {count} {time_word}.",
        ]
    elif count <= 3:
        pool = [
            f"{actor.mention} has now succ’d {target.mention} {count} {time_word}!",
            f"{actor.mention} keeps succ’ing {target.mention} — {count} {time_word} now!",
            f"{count} {time_word} in, and {actor.mention} isn’t easing up on {target.mention}.",
        ]
    elif count <= 6:
        pool = [
            f"{actor.mention} is not subtle — {count} {time_word} on {target.mention}!",
            f"{count} {time_word} now… {actor.mention} is making a point with {target.mention}.",
            f"{actor.mention} keeps coming back — {count} {time_word} and counting.",
        ]
    else:
        pool = [
            f"{count} {time_word}. Yeah. {actor.mention} is absolutely locked in on {target.mention}.",
            f"{actor.mention} has lost count — but it’s at least {count} {time_word}.",
            f"{actor.mention} keeps succ’ing {target.mention}. Nobody’s pretending anymore ({count} {time_word}).",
        ]
    return random.choice(pool)

# =========================
# SQLITE (stats + persistent dedup)
# =========================
class StatsDB:
    def __init__(self, path: str):
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        dirn = os.path.dirname(self.path)
        if dirn:
            os.makedirs(dirn, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    action TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    given INTEGER NOT NULL DEFAULT 0,
                    received INTEGER NOT NULL DEFAULT 0,
                    backs INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (action, user_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_md5 (
                    md5 TEXT PRIMARY KEY,
                    site TEXT NOT NULL,
                    first_seen INTEGER NOT NULL
                )
            """)
            conn.commit()

    async def _run(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    async def record_action(self, action: str, actor_id: int, target_id: int, is_back: bool):
        def work():
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO stats(action, user_id, given, received, backs) VALUES(?, ?, 0, 0, 0)",
                    (action, str(actor_id)),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO stats(action, user_id, given, received, backs) VALUES(?, ?, 0, 0, 0)",
                    (action, str(target_id)),
                )

                if is_back:
                    conn.execute(
                        "UPDATE stats SET given = given + 1, backs = backs + 1 WHERE action = ? AND user_id = ?",
                        (action, str(actor_id)),
                    )
                else:
                    conn.execute(
                        "UPDATE stats SET given = given + 1 WHERE action = ? AND user_id = ?",
                        (action, str(actor_id)),
                    )

                conn.execute(
                    "UPDATE stats SET received = received + 1 WHERE action = ? AND user_id = ?",
                    (action, str(target_id)),
                )
                conn.commit()

        await self._run(work)

    async def get_user(self, action: str, user_id: int) -> dict:
        def work():
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO stats(action, user_id, given, received, backs) VALUES(?, ?, 0, 0, 0)",
                    (action, str(user_id)),
                )
                row = conn.execute(
                    "SELECT given, received, backs FROM stats WHERE action = ? AND user_id = ?",
                    (action, str(user_id)),
                ).fetchone()
                conn.commit()
                return {"given": row[0], "received": row[1], "backs": row[2]}

        return await self._run(work)

    async def mark_seen(self, md5: str, site: str):
        def work():
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO seen_md5(md5, site, first_seen) VALUES (?, ?, ?)",
                    (md5, site, int(time.time())),
                )
                conn.commit()

        await self._run(work)

    async def load_recent_seen(self, max_age_days: int = 30) -> set[str]:
        cutoff = int(time.time()) - max_age_days * 86400

        def work():
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT md5 FROM seen_md5 WHERE first_seen >= ?",
                    (cutoff,),
                ).fetchall()
                return {r[0] for r in rows if r and r[0]}

        return await self._run(work)

STATS_DB = StatsDB(DB_PATH)

# =========================
# PER-INTERACTION DEDUP
# =========================
class InteractionSeen:
    def __init__(self):
        self.md5s: set[str] = set()

    def add(self, md5: str | None):
        if md5:
            self.md5s.add(md5)

    def has(self, md5: str | None) -> bool:
        return bool(md5) and md5 in self.md5s

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
# GELBOORU FETCH (JSON) -> (url, md5, site)
# =========================
async def fetch_image_gelbooru(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
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
                    "pid": random.randint(0, pid_max),
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
                            log.debug("[GEL FETCH] tier=%s limit=%s pid<=%s status=%s", tier_label, limit, pid_max, http_status)
                            log.debug("[GEL FETCH] url=%s", resp.url)

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

        log.debug("[GEL FETCH] tier=%s lowering score tier -> next", tier_label)

    return None

# =========================
# RULE34 FETCH (XML) -> (url, md5, site)
# =========================
async def fetch_image_rule34(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
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
                            log.debug("[R34 FETCH] tier=%s limit=%s pid<=%s status=%s", tier_label, limit, pid_max, http_status)
                            log.debug("[R34 FETCH] url=%s", resp.url)

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

        log.debug("[R34 FETCH] tier=%s lowering score tier -> next", tier_label)

    return None

# =========================
# WRAPPER: Gelbooru -> Rule34
# =========================
async def fetch_image(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    res = await fetch_image_gelbooru(tags, avoid_md5s)
    if res:
        return res
    return await fetch_image_rule34(tags, avoid_md5s)

# =========================
# IMAGE DOWNLOAD + PIL CONVERT (OFF LOOP)
# =========================
async def process_image(url: str, max_attempts: int = 3) -> discord.File | None:
    if not url:
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]

    def pil_work(raw_bytes: bytes) -> discord.File | None:
        try:
            image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            image.thumbnail((2048, 2048))

            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=85, optimize=True)
            buf.seek(0)

            if buf.getbuffer().nbytes > 8_000_000:
                return None

            return discord.File(buf, filename="action.jpg", spoiler=True)
        except Exception as e:
            log.warning("[IMG PROCESS] PIL error: %s: %s", type(e).__name__, e)
            return None

    for attempt in range(1, max_attempts + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    log.debug("[IMG FETCH] attempt=%s/%s status=%s", attempt, max_attempts, resp.status)

                    if resp.status == 429:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue
                    if resp.status != 200:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue

                    raw = await resp.read()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            log.debug("[IMG FETCH] exception=%s: %s — sleeping %ss", type(e).__name__, e, wait)
            await asyncio.sleep(wait)
            continue

        if len(raw) > 24_000_000:
            return None

        return await asyncio.to_thread(pil_work, raw)

    return None

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

# =========================
# VIEWS
# =========================
class PlapBackView(discord.ui.View):
    def __init__(self, original_actor: discord.User, original_target: discord.User):
        super().__init__(timeout=3600)
        self.original_actor = original_actor
        self.original_target = original_target
        self.count = 1
        self.message: discord.Message | None = None
        self.seen = InteractionSeen()

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
                item.label = "Expired"
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="Reroll (3)", emoji="🎲", style=discord.ButtonStyle.secondary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        # Only the original actor can reroll their own message
        if interaction.user.id != self.original_actor.id:
            await interaction.followup.send("Only the sender can reroll 🎲", ephemeral=True)
            return

        remaining = getattr(self, "rerolls_left", 3)
        if remaining <= 0:
            await interaction.followup.send("No rerolls left for this message 😤", ephemeral=True)
            return

        tags = build_tag_ladder(PLAP_BASE, PLAP_POSITIVE_SETS)
        picked = await pick_image(tags, self.seen)
        if not picked:
            await interaction.followup.send("Couldn’t fetch a new image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5, site = picked
        file = await process_image(image_url, max_attempts=3)
        if not file:
            await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
            return

        self.seen.add(md5)
        self.rerolls_left = remaining - 1
        button.label = f"Reroll ({self.rerolls_left})"

        line = random.choice(PLAP_LINES_INTIMATE_NATURAL).format(actor=self.original_actor.mention, target=self.original_target.mention)
        summary = plap_summary(self.original_actor, self.original_target, 1)

        embed = discord.Embed(
            description=f"{line}\n\n**{summary}**\n\n`source: {site}`",
            color=discord.Color.from_rgb(255, 182, 193),
        )
        embed.set_author(name=f"{self.original_actor.display_name} used /plap", icon_url=self.original_actor.display_avatar.url)
        embed.set_image(url="attachment://action.jpg")

        try:
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, attachments=[file], view=self)
        except Exception:
            await interaction.followup.send(embed=embed, file=file, view=self)

    @discord.ui.button(label="Plap back", emoji="👋", style=discord.ButtonStyle.success)
    async def plap_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        if interaction.user.id != self.original_target.id:
            await interaction.followup.send("Not for you 😤", ephemeral=True)
            return

        tags = build_tag_ladder(PLAP_BASE, PLAP_POSITIVE_SETS)
        picked = await pick_image(tags, self.seen)
        if not picked:
            await interaction.followup.send("Couldn’t fetch a new image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5, site = picked
        file = await process_image(image_url, max_attempts=3)
        if not file:
            await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
            return

        self.seen.add(md5)
        self.count += 1
        await STATS_DB.record_action("plap", interaction.user.id, self.original_actor.id, is_back=True)

        line = random.choice(PLAP_LINES_INTIMATE_NATURAL).format(actor=interaction.user.mention, target=self.original_actor.mention)
        summary = plap_summary(interaction.user, self.original_actor, self.count)

        full_embed = discord.Embed(
            description=f"{line}\n\n**{summary}**\n\n`source: {site}`",
            color=discord.Color.from_rgb(173, 216, 230),
        )
        full_embed.set_author(name=f"{interaction.user.display_name} plaps back", icon_url=interaction.user.display_avatar.url)
        full_embed.set_image(url="attachment://action.jpg")

        button.label = f"Plapped ({self.count})"
        try:
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            self.message = interaction.message
        except Exception:
            pass

        await interaction.followup.send(embed=full_embed, file=file)

class SuccBackView(discord.ui.View):
    def __init__(self, original_actor: discord.User, original_target: discord.User):
        super().__init__(timeout=3600)
        self.original_actor = original_actor
        self.original_target = original_target
        self.count = 1
        self.message: discord.Message | None = None
        self.seen = InteractionSeen()

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
                item.label = "Expired"
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="Reroll (3)", emoji="🎲", style=discord.ButtonStyle.secondary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        if interaction.user.id != self.original_actor.id:
            await interaction.followup.send("Only the sender can reroll 🎲", ephemeral=True)
            return

        remaining = getattr(self, "rerolls_left", 3)
        if remaining <= 0:
            await interaction.followup.send("No rerolls left for this message 😤", ephemeral=True)
            return

        tags = build_tag_ladder(SUCC_BASE, SUCC_POSITIVE_SETS)
        picked = await pick_image(tags, self.seen)
        if not picked:
            await interaction.followup.send("Couldn’t fetch a new image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5, site = picked
        file = await process_image(image_url, max_attempts=3)
        if not file:
            await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
            return

        self.seen.add(md5)
        self.rerolls_left = remaining - 1
        button.label = f"Reroll ({self.rerolls_left})"

        line = random.choice(SUCC_LINES_INTIMATE).format(actor=self.original_actor.mention, target=self.original_target.mention)
        summary = succ_summary(self.original_actor, self.original_target, 1)

        embed = discord.Embed(
            description=f"{line}\n\n**{summary}**\n\n`source: {site}`",
            color=discord.Color.from_rgb(199, 21, 133),
        )
        embed.set_author(name=f"{self.original_actor.display_name} used /succ", icon_url=self.original_actor.display_avatar.url)
        embed.set_image(url="attachment://action.jpg")

        try:
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, attachments=[file], view=self)
        except Exception:
            await interaction.followup.send(embed=embed, file=file, view=self)

    @discord.ui.button(label="Succ back", emoji="🫦", style=discord.ButtonStyle.danger)
    async def succ_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        if interaction.user.id != self.original_target.id:
            await interaction.followup.send("Not for you 😤", ephemeral=True)
            return

        tags = build_tag_ladder(SUCC_BASE, SUCC_POSITIVE_SETS)
        picked = await pick_image(tags, self.seen)
        if not picked:
            await interaction.followup.send("Couldn’t fetch a new image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5, site = picked
        file = await process_image(image_url, max_attempts=3)
        if not file:
            await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
            return

        self.seen.add(md5)
        self.count += 1
        await STATS_DB.record_action("succ", interaction.user.id, self.original_actor.id, is_back=True)

        line = random.choice(SUCC_LINES_INTIMATE).format(actor=interaction.user.mention, target=self.original_actor.mention)
        summary = succ_summary(interaction.user, self.original_actor, self.count)

        full_embed = discord.Embed(
            description=f"{line}\n\n**{summary}**\n\n`source: {site}`",
            color=discord.Color.from_rgb(255, 105, 180),
        )
        full_embed.set_author(name=f"{interaction.user.display_name} succs back", icon_url=interaction.user.display_avatar.url)
        full_embed.set_image(url="attachment://action.jpg")

        button.label = f"Succ’d ({self.count})"
        try:
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            self.message = interaction.message
        except Exception:
            pass

        await interaction.followup.send(embed=full_embed, file=file)

# =========================
# /plap (DM ONLY)
# =========================
@bot.tree.command(name="plap", description="Plap another user (DM only)")
@app_commands.allowed_contexts(dms=True, guilds=False, private_channels=True)
@app_commands.allowed_installs(users=True, guilds=False)
async def plap(interaction: discord.Interaction, target: discord.User):
    # ACK FIRST (avoid 10062)
    ok = await safe_defer(interaction, thinking=True)
    if not ok:
        return

    log.info("[CMD] /plap actor=%s target=%s", interaction.user.id, target.id)

    if target.id == interaction.user.id:
        await interaction.followup.send("Not yourself 😅", ephemeral=True)
        return

    view = PlapBackView(interaction.user, target)

    tags = build_tag_ladder(PLAP_BASE, PLAP_POSITIVE_SETS)
    picked = await pick_image(tags, view.seen)
    if not picked:
        await interaction.followup.send("Couldn’t fetch an image right now 😭 Try again.", ephemeral=True)
        return

    image_url, md5, site = picked
    file = await process_image(image_url, max_attempts=3)
    if not file:
        await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
        return

    view.seen.add(md5)
    await STATS_DB.record_action("plap", interaction.user.id, target.id, is_back=False)

    line = random.choice(PLAP_LINES_INTIMATE_NATURAL).format(actor=interaction.user.mention, target=target.mention)
    summary = plap_summary(interaction.user, target, 1)

    embed = discord.Embed(
        description=f"{line}\n\n**{summary}**\n\n`source: {site}`",
        color=discord.Color.from_rgb(255, 182, 193),
    )
    embed.set_author(name=f"{interaction.user.display_name} used /plap", icon_url=interaction.user.display_avatar.url)
    embed.set_image(url="attachment://action.jpg")

    msg = await interaction.followup.send(embed=embed, file=file, view=view, wait=True)
    view.message = msg

# =========================
# /succ (DM ONLY)
# =========================
@bot.tree.command(name="succ", description="Succ another user (DM only)")
@app_commands.allowed_contexts(dms=True, guilds=False, private_channels=True)
@app_commands.allowed_installs(users=True, guilds=False)
async def succ(interaction: discord.Interaction, target: discord.User):
    # ACK FIRST (avoid 10062)
    ok = await safe_defer(interaction, thinking=True)
    if not ok:
        return

    log.info("[CMD] /succ actor=%s target=%s", interaction.user.id, target.id)

    if target.id == interaction.user.id:
        await interaction.followup.send("Not yourself 😅", ephemeral=True)
        return

    view = SuccBackView(interaction.user, target)

    tags = build_tag_ladder(SUCC_BASE, SUCC_POSITIVE_SETS)
    picked = await pick_image(tags, view.seen)
    if not picked:
        await interaction.followup.send("Couldn’t fetch an image right now 😭 Try again.", ephemeral=True)
        return

    image_url, md5, site = picked
    file = await process_image(image_url, max_attempts=3)
    if not file:
        await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
        return

    view.seen.add(md5)
    await STATS_DB.record_action("succ", interaction.user.id, target.id, is_back=False)

    line = random.choice(SUCC_LINES_INTIMATE).format(actor=interaction.user.mention, target=target.mention)
    summary = succ_summary(interaction.user, target, 1)

    embed = discord.Embed(
        description=f"{line}\n\n**{summary}**\n\n`source: {site}`",
        color=discord.Color.from_rgb(199, 21, 133),
    )
    embed.set_author(name=f"{interaction.user.display_name} used /succ", icon_url=interaction.user.display_avatar.url)
    embed.set_image(url="attachment://action.jpg")

    msg = await interaction.followup.send(embed=embed, file=file, view=view, wait=True)
    view.message = msg

# =========================
# /stats (DM ONLY) - COMBINED
# FIXED: defer first + followup (prevents 10062)
# =========================
@bot.tree.command(name="stats", description="View plap + succ stats (DM only)")
@app_commands.allowed_contexts(dms=True, guilds=False, private_channels=True)
@app_commands.allowed_installs(users=True, guilds=False)
async def stats(interaction: discord.Interaction, user: discord.User | None = None):
    ok = await safe_defer(interaction, thinking=False)
    if not ok:
        return

    user = user or interaction.user
    pl = await STATS_DB.get_user("plap", user.id)
    su = await STATS_DB.get_user("succ", user.id)

    embed = discord.Embed(
        title="📊 Stats",
        description=(
            f"**User:** {user.mention}\n\n"
            f"**👋 Plap**\n"
            f"• **Given:** {pl['given']}\n"
            f"• **Received:** {pl['received']}\n"
            f"• **Backs:** {pl['backs']}\n\n"
            f"**🫦 Succ**\n"
            f"• **Given:** {su['given']}\n"
            f"• **Received:** {su['received']}\n"
            f"• **Backs:** {su['backs']}"
        ),
        color=discord.Color.blurple(),
    )
    embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    await interaction.followup.send(embed=embed, ephemeral=True)

# =========================
# READY
# =========================
@bot.event
async def on_ready():
    await bot.tree.sync()  # global sync for DMs
    log.info("Logged in as %s", bot.user)
    log.info("Registered commands: %s", [c.name for c in bot.tree.get_commands()])

if __name__ == "__main__":
    bot.run(TOKEN)
