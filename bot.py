import random
import aiohttp
import io
import logging
import json
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
# SCORE FALLBACK TIERS
# =========================
SCORE_TIERS = [
    "score:>50",
    "score:>40",
    "score:>30",
    "score:>20",
    "",  # final fallback: no score filter
]

# =========================
# TAGS (EDIT FREELY)
# =========================
PLAP_TAGS = "futa_on_female sex_from_behind -video -gif -loli -shota -young -underage -child -minor -kid -furry -anthro -feral -animal -bestiality -rape -raped -nonconsensual -forced -dubious_consent -incest -family -gore -blood -death -scat -watersports -vomit -diaper -inflation -vore -oviposition -egg -pregnant -birth -lactation"
SUCC_TAGS = "futa_on_female oral -video -gif -loli -shota -young -underage -child -minor -kid -furry -anthro -feral -animal -bestiality -rape -raped -nonconsensual -forced -dubious_consent -incest -family -gore -blood -death -scat -watersports -vomit -diaper -inflation -vore -oviposition -egg -pregnant -birth -lactation"


if not TOKEN:
    logging.warning("TOKEN is missing! The bot will not be able to log in.")
if not RULE34_API_KEY or not RULE34_USER_ID:
    logging.warning("RULE34_API_KEY or RULE34_USER_ID missing! Rule34 image fetching will fail.")
if not GELBOORU_API_KEY or not GELBOORU_USER_ID:
    logging.warning("GELBOORU_API_KEY or GELBOORU_USER_ID missing! Gelbooru fetching will be skipped.")

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# PLAP LINES (SEPARATE)
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
# SUCC LINES (SEPARATE)
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
# ESCALATING SUMMARY LINES (SEPARATE)
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
        os.makedirs(os.path.dirname(self.path), exist_ok=True) if os.path.dirname(self.path) else None
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    action TEXT NOT NULL,            -- 'plap' or 'succ'
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
# PER-SITE PID TUNING
# (stricter tiers -> smaller pid range -> fewer empty pages)
# =========================
def pid_max_for(site: str, score_tag: str) -> int:
    # You can tweak these anytime
    if site == "gelbooru":
        if score_tag == "score:>50":
            return 20
        if score_tag == "score:>40":
            return 30
        if score_tag == "score:>30":
            return 45
        if score_tag == "score:>20":
            return 70
        return 140  # no-score tier: broad results
    else:  # rule34
        if score_tag == "score:>50":
            return 25
        if score_tag == "score:>40":
            return 40
        if score_tag == "score:>30":
            return 60
        if score_tag == "score:>20":
            return 90
        return 180  # no-score tier: very broad

# =========================
# GELBOORU FETCH (JSON)
# Lowers score on: timeouts, 429s, parse errors, temp network issues, 0 posts
# =========================
async def fetch_image_gelbooru(tags: str, max_attempts: int = 5) -> str | None:
    if not GELBOORU_API_KEY or not GELBOORU_USER_ID:
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]

    for score_tag in SCORE_TIERS:
        full_tags = f"{tags} {score_tag}".strip()
        tier_label = score_tag or "no-score"
        pid_max = pid_max_for("gelbooru", score_tag)

        print(f"[GEL FETCH] Trying tier='{tier_label}' pid_max={pid_max} tags='{full_tags}'")

        for attempt in range(1, max_attempts + 1):
            params = {
                "limit": 1,
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
                        print(f"[GEL FETCH] tier={tier_label} attempt={attempt}/{max_attempts} status={resp.status}")

                        if resp.status == 429:
                            await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                            break
                        if resp.status != 200:
                            await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                            break

                        data = await resp.json(content_type=None)

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"[GEL FETCH] tier={tier_label} exception={type(e).__name__}: {e} (lowering score)")
                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                break
            except Exception as e:
                print(f"[GEL FETCH] tier={tier_label} JSON parse error: {type(e).__name__}: {e} (lowering score)")
                break

            posts = None
            if isinstance(data, dict):
                posts = data.get("post")
            elif isinstance(data, list):
                posts = data

            if not posts:
                print(f"[GEL FETCH] tier={tier_label} 0 posts (lowering score)")
                break

            if isinstance(posts, dict):
                posts = [posts]

            valid = [p for p in posts if isinstance(p, dict) and p.get("file_url")]
            if not valid:
                print(f"[GEL FETCH] tier={tier_label} no file_url posts (lowering score)")
                break

            return random.choice(valid).get("file_url")

        print(f"[GEL FETCH] Dropping from tier '{tier_label}' → next tier")

    return None

# =========================
# RULE34 FETCH (XML)
# Lowers score on: timeouts, 429s, parse errors, temp network issues, 0 posts
# =========================
async def fetch_image_rule34(tags: str, max_attempts: int = 5) -> str | None:
    backoffs = [0.0, 1.0, 2.5, 5.0]

    if not RULE34_API_KEY or not RULE34_USER_ID:
        print("[R34 FETCH] Missing RULE34_API_KEY or RULE34_USER_ID env vars.")
        return None

    for score_tag in SCORE_TIERS:
        full_tags = f"{tags} {score_tag}".strip()
        tier_label = score_tag or "no-score"
        pid_max = pid_max_for("rule34", score_tag)

        print(f"[R34 FETCH] Trying tier='{tier_label}' pid_max={pid_max} tags='{full_tags}'")

        for attempt in range(1, max_attempts + 1):
            params = {
                "limit": 1,
                "pid": random.randint(0, pid_max),
                "tags": full_tags,
                "api_key": RULE34_API_KEY,
                "user_id": RULE34_USER_ID,
            }

            try:
                async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
                    async with session.get(
                        BOORU_API,
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        print(f"[R34 FETCH] tier={tier_label} attempt={attempt}/{max_attempts} status={resp.status} url={resp.url}")

                        if resp.status == 429:
                            await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                            break

                        if resp.status != 200:
                            await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                            break

                        xml = await resp.text()

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"[R34 FETCH] tier={tier_label} exception={type(e).__name__}: {e} (lowering score)")
                await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                break

            try:
                root = ET.fromstring(xml)
            except ET.ParseError as e:
                print(f"[R34 FETCH] tier={tier_label} XML parse error: {e} (lowering score)")
                break

            posts = root.findall("post")
            if not posts:
                print(f"[R34 FETCH] tier={tier_label} 0 posts (lowering score)")
                break

            valid_posts = [p for p in posts if p.attrib.get("file_url")]
            if not valid_posts:
                print(f"[R34 FETCH] tier={tier_label} no file_url posts (lowering score)")
                break

            post = random.choice(valid_posts)
            return post.attrib.get("file_url")

        print(f"[R34 FETCH] Dropping from tier '{tier_label}' → next tier")

    return None

# =========================
# WRAPPER: Gelbooru -> fallback to Rule34
# =========================
async def fetch_image(tags: str, max_attempts: int = 5) -> str | None:
    url = await fetch_image_gelbooru(tags, max_attempts=max_attempts)
    if url:
        return url
    return await fetch_image_rule34(tags, max_attempts=max_attempts)

# =========================
# IMAGE DOWNLOAD + CONVERT (SPOILER)
# =========================
async def process_image(url: str, max_attempts: int = 3) -> discord.File | None:
    if not url:
        return None

    backoffs = [0.0, 1.0, 2.5, 5.0]

    for attempt in range(1, max_attempts + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    print(f"[IMG FETCH] attempt={attempt}/{max_attempts} status={resp.status} url={resp.url}")

                    if resp.status == 429:
                        wait = backoffs[min(attempt, len(backoffs) - 1)]
                        await asyncio.sleep(wait)
                        continue

                    if resp.status != 200:
                        wait = backoffs[min(attempt, len(backoffs) - 1)]
                        await asyncio.sleep(wait)
                        continue

                    raw = await resp.read()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            print(f"[IMG FETCH] exception={type(e).__name__}: {e} — sleeping {wait}s")
            await asyncio.sleep(wait)
            continue

        if len(raw) > 24_000_000:
            return None

        try:
            image = Image.open(io.BytesIO(raw)).convert("RGB")
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

        await interaction.response.defer(thinking=True)

        image_url = await fetch_image(PLAP_TAGS, max_attempts=5)
        if not image_url:
            await interaction.followup.send("Couldn’t fetch an image right now 😭 Try again.", ephemeral=True)
            return

        file = await process_image(image_url, max_attempts=3)
        if not file:
            await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
            return

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
        button.disabled = False

        try:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                view=self,
            )
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

        await interaction.response.defer(thinking=True)

        image_url = await fetch_image(SUCC_TAGS, max_attempts=5)
        if not image_url:
            await interaction.followup.send("Couldn’t fetch an image right now 😭 Try again.", ephemeral=True)
            return

        file = await process_image(image_url, max_attempts=3)
        if not file:
            await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
            return

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
        button.disabled = False

        try:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                view=self,
            )
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

    await interaction.response.defer(thinking=True)

    image_url = await fetch_image(PLAP_TAGS, max_attempts=5)
    if not image_url:
        await interaction.followup.send("Couldn’t fetch an image right now 😭 Try again.", ephemeral=True)
        return

    file = await process_image(image_url, max_attempts=3)
    if not file:
        await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
        return

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

    view = PlapBackView(interaction.user, target)
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

    await interaction.response.defer(thinking=True)

    image_url = await fetch_image(SUCC_TAGS, max_attempts=5)
    if not image_url:
        await interaction.followup.send("Couldn’t fetch an image right now 😭 Try again.", ephemeral=True)
        return

    file = await process_image(image_url, max_attempts=3)
    if not file:
        await interaction.followup.send("Image failed 😭 (download/convert)", ephemeral=True)
        return

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

    view = SuccBackView(interaction.user, target)
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
