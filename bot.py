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

TOKEN = "MTQ0OTg0MDM2Mzg3MDM1OTc2Mw.GJ_Y_k.Grssi02jlFr4J1T1Wrd1JI73xO17qTlEZLZUcg"
BOORU_API = "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index"
USER_AGENT = "Rule34DiscordBot/1.0"
RULE34_API_KEY = "a8a50348e0754ddbee7de5e869427460b1e424c0109130d53d169bf0cb99c21827b2222c2c3c59352c7a1b847b0d1e869838aee87a59a2d2bddb6811bbbdcae8"
RULE34_USER_ID = "5699450"

# Put this on a Railway Volume for persistence, e.g. /data/stats.sqlite3
DB_PATH = "/data/stats.sqlite3" or "stats.sqlite3"

# =========================
# TAGS (EDIT FREELY)
# Add safety excludes to reduce accidental underage content.
# =========================
PLAP_TAGS = "futa_on_female ass_slap -video -gif -loli -shota -young -underage -child -minor -kid-furry -anthro -feral -animal -bestiality -rape -raped -nonconsensual -forced -dubious_consent -incest -family -gore -blood -death -scat -watersports -vomit -diaper -inflation -vore -oviposition -egg -pregnant -birth -lactation"
SUCC_TAGS = "futa_on_female oral -video -gif -loli -shota -young -underage -child -minor -kid -furry -anthro -feral -animal -bestiality -rape -raped -nonconsensual -forced -dubious_consent -incest -family -gore -blood -death -scat -watersports -vomit -diaper -inflation -vore -oviposition -egg -pregnant -birth -lactation"

if not TOKEN:
    logging.warning("TOKEN is missing! The bot will not be able to log in.")
if not RULE34_API_KEY or not RULE34_USER_ID:
    logging.warning("RULE34_API_KEY or RULE34_USER_ID missing! Image fetching will fail.")

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
# RULE34 FETCH (PARAMETRIZED)
# =========================
async def fetch_image(tags: str, max_attempts: int = 3) -> str | None:
    backoffs = [0.0, 1.0, 2.5, 5.0]

    if not RULE34_API_KEY or not RULE34_USER_ID:
        print("[R34 FETCH] Missing RULE34_API_KEY or RULE34_USER_ID env vars.")
        return None

    for attempt in range(1, max_attempts + 1):
        params = {
            "limit": 1,
            "pid": random.randint(0, 80),
            "tags": tags,
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
                    print(f"[R34 FETCH] attempt={attempt}/{max_attempts} status={resp.status} url={resp.url}")

                    if resp.status == 429:
                        wait = backoffs[min(attempt, len(backoffs) - 1)]
                        await asyncio.sleep(wait)
                        continue

                    if resp.status != 200:
                        wait = backoffs[min(attempt, len(backoffs) - 1)]
                        await asyncio.sleep(wait)
                        continue

                    xml = await resp.text()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            print(f"[R34 FETCH] exception={type(e).__name__}: {e} — sleeping {wait}s")
            await asyncio.sleep(wait)
            continue

        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            await asyncio.sleep(wait)
            continue

        posts = root.findall("post")
        if not posts:
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            await asyncio.sleep(wait)
            continue

        valid_posts = [p for p in posts if p.attrib.get("file_url")]
        if not valid_posts:
            wait = backoffs[min(attempt, len(backoffs) - 1)]
            await asyncio.sleep(wait)
            continue

        post = random.choice(valid_posts)
        return post.attrib.get("file_url")

    return None

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
# NOTE: Your deployed discord.py build can't swap attachments via Message.edit(files=...).
# So we:
# 1) Update the button label/count on the ORIGINAL message
# 2) Send a NEW message that contains the FULL embed (text + count) + the NEW spoiler image
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

        image_url = await fetch_image(PLAP_TAGS, max_attempts=3)
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

        # Edit ORIGINAL message's view so the label/count updates (no attachments)
        try:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                view=self,
            )
            self.message = interaction.message
        except Exception:
            pass

        # Send FULL embed + spoiler image as a new message
        await interaction.followup.send(embed=full_embed, file=file)

# =========================
# SUCC BACK VIEW (same logic)
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

        image_url = await fetch_image(SUCC_TAGS, max_attempts=3)
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

    image_url = await fetch_image(PLAP_TAGS, max_attempts=3)
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

    image_url = await fetch_image(SUCC_TAGS, max_attempts=3)
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
