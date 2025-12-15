import random
import aiohttp
import io
import logging
import os
import asyncio
import sqlite3
import discord
import xml.etree.ElementTree as ET
from discord.ext import commands
from discord import app_commands
from PIL import Image

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)

# =========================
# SECRETS (SET AS ENV VARS)
# Railway Variables:
# TOKEN
# RULE34_API_KEY
# RULE34_USER_ID
# GELBOORU_API_KEY
# GELBOORU_USER_ID
# =========================
TOKEN = "MTQ0OTg0MDM2Mzg3MDM1OTc2Mw.GJ_Y_k.Grssi02jlFr4J1T1Wrd1JI73xO17qTlEZLZUcg"

# Rule34 (XML)
BOORU_API = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index"
USER_AGENT = "Rule34DiscordBot/1.0"
RULE34_API_KEY = "a8a50348e0754ddbee7de5e869427460b1e424c0109130d53d169bf0cb99c21827b2222c2c3c59352c7a1b847b0d1e869838aee87a59a2d2bddb6811bbbdcae8"
RULE34_USER_ID = "5699450"

# Gelbooru JSON API endpoint
GELBOORU_API = "https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1"
GELBOORU_API_KEY = "04176dbed5e2dcb5f047e9b684af9fac71df32281b10c92efff66da5dc97bd4710f78a81d87dd29d2670b97c6b1768f153902124648253b62fff50b85ea1049e"
GELBOORU_USER_ID = "1873378"

# Put this on a Railway Volume for persistence, e.g. /data/stats.sqlite3
# (kept your intent/structure)
DB_PATH = "/data/stats.sqlite3" or "stats.sqlite3"

# =========================
# TAGS (EDIT FREELY)
# =========================
PLAP_TAGS = "futa_on_female sex_from_behind -video -gif -loli -shota -young -underage -child -minor -kid -furry -anthro -feral -animal -bestiality -rape -raped -nonconsensual -forced -dubious_consent -incest -family -gore -blood -death -scat -watersports -vomit -diaper -inflation -vore -oviposition -egg -pregnant -birth -lactation"
SUCC_TAGS = "futa_on_female oral -video -gif -loli -shota -young -underage -child -minor -kid -furry -anthro -feral -animal -bestiality -rape -raped -nonconsensual -forced -dubious_consent -incest -family -gore -blood -death -scat -watersports -vomit -diaper -inflation -vore -oviposition -egg -pregnant -birth -lactation"


if not TOKEN:
    logging.warning("TOKEN missing! Bot cannot log in.")
if not RULE34_API_KEY or not RULE34_USER_ID:
    logging.warning("RULE34_API_KEY or RULE34_USER_ID missing! Rule34 fetching will fail.")
if not GELBOORU_API_KEY or not GELBOORU_USER_ID:
    logging.warning("GELBOORU_API_KEY or GELBOORU_USER_ID missing! Gelbooru fetching will be skipped.")

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

# Adaptive limit ladder (backs off when caps/429/timeouts/parse issues happen)
LIMIT_TIERS = [25, 15, 10, 5, 1]

# How many different pids/pages to try per (score tier + limit tier)
PAGES_PER_LIMIT = 3

# How many times to re-pull if we keep hitting duplicates (md5) in the same interaction
DEDUP_PULL_TRIES = 5

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# SAFE DEFER (helps prevent Unknown interaction / 10062)
# =========================
async def safe_defer(interaction: discord.Interaction, *, thinking: bool = True) -> bool:
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=thinking)
        return True
    except discord.NotFound:
        return False
    except Exception:
        return False

def should_lower_limit(http_status: int | None, exc: Exception | None, parse_failed: bool) -> bool:
    if parse_failed:
        return True
    if exc is not None:
        return True
    if http_status in (429, 500, 502, 503, 504):
        return True
    # Some endpoints complain when params/response are too big or malformed
    if http_status in (400, 413, 414, 422):
        return True
    return False

# =========================
# PLAP LINES
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

# =========================
# SUCC LINES
# =========================
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

# =========================
# ESCALATING SUMMARY LINES
# =========================
def plap_summary(actor: discord.User, target: discord.User, count: int) -> str:
    time_word = "time" if count == 1 else "times"
    tier_1 = [
        f"{actor.mention} plapped {target.mention} {count} {time_word}!",
        f"{actor.mention} has plapped {target.mention} {count} {time_word}.",
    ]
    tier_2 = [
        f"{actor.mention} has now plapped {target.mention} {count} {time_word}!",
        f"{actor.mention} keeps plapping {target.mention} — {count} {time_word} now!",
        f"{count} {time_word} in, and {actor.mention} isn’t stopping with {target.mention}.",
    ]
    tier_3 = [
        f"{actor.mention} is on a roll — {count} {time_word} on {target.mention}!",
        f"{count} {time_word} now… {actor.mention} is clearly committed to {target.mention}.",
        f"{actor.mention} keeps coming back — {count} {time_word} and counting.",
    ]
    tier_4 = [
        f"{count} {time_word}. Yeah. {actor.mention} is absolutely not done with {target.mention}.",
        f"{actor.mention} has lost count — but it’s at least {count} {time_word}.",
        f"{actor.mention} keeps plapping {target.mention}. Nobody’s pretending anymore ({count} {time_word}).",
    ]
    if count <= 1:
        pool = tier_1
    elif count <= 3:
        pool = tier_2
    elif count <= 6:
        pool = tier_3
    else:
        pool = tier_4
    return random.choice(pool)

def succ_summary(actor: discord.User, target: discord.User, count: int) -> str:
    time_word = "time" if count == 1 else "times"
    tier_1 = [
        f"{actor.mention} succ’d {target.mention} {count} {time_word}!",
        f"{actor.mention} has succ’d {target.mention} {count} {time_word}.",
    ]
    tier_2 = [
        f"{actor.mention} has now succ’d {target.mention} {count} {time_word}!",
        f"{actor.mention} keeps succ’ing {target.mention} — {count} {time_word} now!",
        f"{count} {time_word} in, and {actor.mention} isn’t easing up on {target.mention}.",
    ]
    tier_3 = [
        f"{actor.mention} is not subtle — {count} {time_word} on {target.mention}!",
        f"{count} {time_word} now… {actor.mention} is making a point with {target.mention}.",
        f"{actor.mention} keeps coming back — {count} {time_word} and counting.",
    ]
    tier_4 = [
        f"{count} {time_word}. Yeah. {actor.mention} is absolutely locked in on {target.mention}.",
        f"{actor.mention} has lost count — but it’s at least {count} {time_word}.",
        f"{actor.mention} keeps succ’ing {target.mention}. Nobody’s pretending anymore ({count} {time_word}).",
    ]
    if count <= 1:
        pool = tier_1
    elif count <= 3:
        pool = tier_2
    elif count <= 6:
        pool = tier_3
    else:
        pool = tier_4
    return random.choice(pool)

# =========================
# SQLITE STATS (PERSISTENT)
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

STATS_DB = StatsDB(DB_PATH)

# =========================
# PER-INTERACTION MD5 DEDUP
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
# PER-SITE PID TUNING
# =========================
def pid_max_for(site: str, score_tag: str) -> int:
    # Wider pid ranges reduces repeats massively
    if site == "gelbooru":
        if score_tag == "score:>50":
            return 120
        if score_tag == "score:>40":
            return 160
        if score_tag == "score:>30":
            return 220
        if score_tag == "score:>20":
            return 300
        return 450
    else:  # rule34
        if score_tag == "score:>50":
            return 120
        if score_tag == "score:>40":
            return 160
        if score_tag == "score:>30":
            return 220
        if score_tag == "score:>20":
            return 300
        return 450

# =========================
# GELBOORU FETCH (JSON) -> returns (url, md5)
# adaptive limit + score tiers
# =========================
async def fetch_image_gelbooru(tags: str, avoid_md5s: set[str] | None = None) -> tuple[str, str | None] | None:
    if not GELBOORU_API_KEY or not GELBOORU_USER_ID:
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]
    avoid_md5s = avoid_md5s or set()

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
                            print(f"[GEL FETCH] tier={tier_label} limit={limit} status={http_status}")

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
                    if md5 and md5 in avoid_md5s:
                        continue
                    return (url, md5)

            print(f"[GEL FETCH] tier={tier_label} lowering limit -> next")

        print(f"[GEL FETCH] tier={tier_label} lowering score tier -> next")

    return None

# =========================
# RULE34 FETCH (XML) -> returns (url, md5)
# adaptive limit + score tiers
# =========================
async def fetch_image_rule34(tags: str, avoid_md5s: set[str] | None = None) -> tuple[str, str | None] | None:
    if not RULE34_API_KEY or not RULE34_USER_ID:
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]
    avoid_md5s = avoid_md5s or set()

    for score_tag in SCORE_TIERS:
        tier_label = score_tag or "no-score"
        full_tags = f"{tags} {score_tag}".strip()
        pid_max = pid_max_for("rule34", score_tag)

        for limit in LIMIT_TIERS:
            for _ in range(PAGES_PER_LIMIT):
                http_status = None
                exc: Exception | None = None
                parse_failed = False
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
                            print(f"[R34 FETCH] tier={tier_label} limit={limit} status={http_status}")

                            if http_status == 429:
                                await asyncio.sleep(backoffs[1])
                                break
                            if http_status != 200:
                                break

                            xml = await resp.text()

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    exc = e

                if should_lower_limit(http_status, exc, parse_failed):
                    if http_status == 429:
                        await asyncio.sleep(backoffs[2])
                    break

                try:
                    root = ET.fromstring(xml or "")
                except ET.ParseError as e:
                    print(f"[R34 FETCH] tier={tier_label} limit={limit} XML parse error: {e}")
                    parse_failed = True
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
                    if md5 and md5 in avoid_md5s:
                        continue
                    return (url, md5)

            print(f"[R34 FETCH] tier={tier_label} lowering limit -> next")

        print(f"[R34 FETCH] tier={tier_label} lowering score tier -> next")

    return None

# =========================
# WRAPPER: Gelbooru -> Rule34
# =========================
async def fetch_image(tags: str, avoid_md5s: set[str] | None = None) -> tuple[str, str | None] | None:
    res = await fetch_image_gelbooru(tags, avoid_md5s=avoid_md5s)
    if res:
        return res
    return await fetch_image_rule34(tags, avoid_md5s=avoid_md5s)

# =========================
# IMAGE DOWNLOAD + PIL CONVERT (OFF EVENT LOOP)
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
            print(f"[IMG PROCESS] PIL error: {type(e).__name__}: {e}")
            return None

    for attempt in range(1, max_attempts + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    print(f"[IMG FETCH] attempt={attempt}/{max_attempts} status={resp.status}")

                    if resp.status == 429:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue

                    if resp.status != 200:
                        await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                        continue

                    raw = await resp.read()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            print(f"[IMG FETCH] exception={type(e).__name__}: {e} — sleeping {wait}s")
            await asyncio.sleep(wait)
            continue

        if len(raw) > 24_000_000:
            return None

        return await asyncio.to_thread(pil_work, raw)

    return None

# =========================
# PLAP BACK VIEW
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

    @discord.ui.button(label="Plap back", emoji="👋", style=discord.ButtonStyle.success)
    async def plap_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.original_target.id:
            await interaction.response.send_message("Not for you 😤", ephemeral=True)
            return

        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        picked: tuple[str, str | None] | None = None
        for _ in range(DEDUP_PULL_TRIES):
            res = await fetch_image(PLAP_TAGS, avoid_md5s=self.seen.md5s)
            if not res:
                break
            url, md5 = res
            if self.seen.has(md5):
                continue
            picked = (url, md5)
            break

        if not picked:
            await interaction.followup.send("Couldn’t fetch a new image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5 = picked

        file = await process_image(image_url, max_attempts=3)
        if not file:
            await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
            return

        self.seen.add(md5)
        self.count += 1
        await STATS_DB.record_action("plap", interaction.user.id, self.original_actor.id, is_back=True)

        line = random.choice(PLAP_LINES_INTIMATE_NATURAL).format(
            actor=interaction.user.mention,
            target=self.original_actor.mention,
        )
        summary = plap_summary(interaction.user, self.original_actor, self.count)

        full_embed = discord.Embed(
            description=f"{line}\n\n**{summary}**",
            color=discord.Color.from_rgb(173, 216, 230),
        )
        full_embed.set_author(
            name=f"{interaction.user.display_name} plaps back",
            icon_url=interaction.user.display_avatar.url,
        )
        full_embed.set_image(url="attachment://action.jpg")

        button.label = f"Plapped ({self.count})"

        # Update the original message's view/label (no attachment edit)
        try:
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            self.message = interaction.message
        except Exception:
            pass

        await interaction.followup.send(embed=full_embed, file=file)

# =========================
# SUCC BACK VIEW
# =========================
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

    @discord.ui.button(label="Succ back", emoji="🫦", style=discord.ButtonStyle.danger)
    async def succ_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.original_target.id:
            await interaction.response.send_message("Not for you 😤", ephemeral=True)
            return

        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        picked: tuple[str, str | None] | None = None
        for _ in range(DEDUP_PULL_TRIES):
            res = await fetch_image(SUCC_TAGS, avoid_md5s=self.seen.md5s)
            if not res:
                break
            url, md5 = res
            if self.seen.has(md5):
                continue
            picked = (url, md5)
            break

        if not picked:
            await interaction.followup.send("Couldn’t fetch a new image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5 = picked

        file = await process_image(image_url, max_attempts=3)
        if not file:
            await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
            return

        self.seen.add(md5)
        self.count += 1
        await STATS_DB.record_action("succ", interaction.user.id, self.original_actor.id, is_back=True)

        line = random.choice(SUCC_LINES_INTIMATE).format(
            actor=interaction.user.mention,
            target=self.original_actor.mention,
        )
        summary = succ_summary(interaction.user, self.original_actor, self.count)

        full_embed = discord.Embed(
            description=f"{line}\n\n**{summary}**",
            color=discord.Color.from_rgb(255, 105, 180),
        )
        full_embed.set_author(
            name=f"{interaction.user.display_name} succs back",
            icon_url=interaction.user.display_avatar.url,
        )
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
    if target.id == interaction.user.id:
        await interaction.response.send_message("Not yourself 😅", ephemeral=True)
        return

    ok = await safe_defer(interaction, thinking=True)
    if not ok:
        return

    # Create view early so we can seed its md5 set with the initial image
    view = PlapBackView(interaction.user, target)

    picked: tuple[str, str | None] | None = None
    for _ in range(DEDUP_PULL_TRIES):
        res = await fetch_image(PLAP_TAGS, avoid_md5s=view.seen.md5s)
        if not res:
            break
        url, md5 = res
        if view.seen.has(md5):
            continue
        picked = (url, md5)
        break

    if not picked:
        await interaction.followup.send("Couldn’t fetch an image right now 😭 Try again.", ephemeral=True)
        return

    image_url, md5 = picked

    file = await process_image(image_url, max_attempts=3)
    if not file:
        await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
        return

    view.seen.add(md5)
    await STATS_DB.record_action("plap", interaction.user.id, target.id, is_back=False)

    line = random.choice(PLAP_LINES_INTIMATE_NATURAL).format(
        actor=interaction.user.mention,
        target=target.mention,
    )
    summary = plap_summary(interaction.user, target, 1)

    embed = discord.Embed(
        description=f"{line}\n\n**{summary}**",
        color=discord.Color.from_rgb(255, 182, 193),
    )
    embed.set_author(
        name=f"{interaction.user.display_name} used /plap",
        icon_url=interaction.user.display_avatar.url,
    )
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
    if target.id == interaction.user.id:
        await interaction.response.send_message("Not yourself 😅", ephemeral=True)
        return

    ok = await safe_defer(interaction, thinking=True)
    if not ok:
        return

    view = SuccBackView(interaction.user, target)

    picked: tuple[str, str | None] | None = None
    for _ in range(DEDUP_PULL_TRIES):
        res = await fetch_image(SUCC_TAGS, avoid_md5s=view.seen.md5s)
        if not res:
            break
        url, md5 = res
        if view.seen.has(md5):
            continue
        picked = (url, md5)
        break

    if not picked:
        await interaction.followup.send("Couldn’t fetch an image right now 😭 Try again.", ephemeral=True)
        return

    image_url, md5 = picked

    file = await process_image(image_url, max_attempts=3)
    if not file:
        await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
        return

    view.seen.add(md5)
    await STATS_DB.record_action("succ", interaction.user.id, target.id, is_back=False)

    line = random.choice(SUCC_LINES_INTIMATE).format(
        actor=interaction.user.mention,
        target=target.mention,
    )
    summary = succ_summary(interaction.user, target, 1)

    embed = discord.Embed(
        description=f"{line}\n\n**{summary}**",
        color=discord.Color.from_rgb(199, 21, 133),
    )
    embed.set_author(
        name=f"{interaction.user.display_name} used /succ",
        icon_url=interaction.user.display_avatar.url,
    )
    embed.set_image(url="attachment://action.jpg")

    msg = await interaction.followup.send(embed=embed, file=file, view=view, wait=True)
    view.message = msg

# =========================
# /stats (DM ONLY) - COMBINED
# =========================
@bot.tree.command(name="stats", description="View plap + succ stats (DM only)")
@app_commands.allowed_contexts(dms=True, guilds=False, private_channels=True)
@app_commands.allowed_installs(users=True, guilds=False)
async def stats(interaction: discord.Interaction, user: discord.User | None = None):
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
    await interaction.response.send_message(embed=embed, ephemeral=True)

# =========================
# READY
# =========================
@bot.event
async def on_ready():
    await bot.tree.sync()  # global sync for DMs
    logging.info("Logged in as %s", bot.user)
    logging.info("Registered commands: %s", [c.name for c in bot.tree.get_commands()])

bot.run(TOKEN)
