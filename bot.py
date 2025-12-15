import random
import aiohttp
import io
import logging
import json
import os
import asyncio
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

# =========================
# TAGS (EDIT FREELY)
# Add safety excludes to reduce accidental underage content.
# =========================
PLAP_TAGS = "futa_on_female ass_slap -video -gif -loli -shota -furry"
SUCC_TAGS = "futa_on_female oral -video -gif -loli -shota -furry"

if not TOKEN:
    logging.warning("DISCORD_TOKEN is missing! The bot will not be able to log in.")
if not RULE34_API_KEY or not RULE34_USER_ID:
    logging.warning("RULE34_API_KEY or RULE34_USER_ID missing! Image fetching will fail.")

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

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
# PERSISTENT STATS (SEPARATE STORES)
# =========================
class StatsStore:
    def __init__(self, path: str):
        self.path = path
        self.data = {"users": {}}
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            self.save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            if "users" not in self.data or not isinstance(self.data["users"], dict):
                self.data = {"users": {}}
        except Exception:
            self.data = {"users": {}}
            self.save()

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logging.exception("Failed to save stats: %r", e)

    def _ensure_user(self, user_id: int):
        uid = str(user_id)
        if uid not in self.data["users"]:
            self.data["users"][uid] = {"given": 0, "received": 0, "backs": 0}
        return self.data["users"][uid]

    def record_action(self, actor_id: int, target_id: int, is_back: bool):
        actor = self._ensure_user(actor_id)
        target = self._ensure_user(target_id)
        actor["given"] += 1
        if is_back:
            actor["backs"] += 1
        target["received"] += 1
        self.save()

    def get_user(self, user_id: int):
        return self._ensure_user(user_id)

PLAP_STATS = StatsStore("plap_stats.json")
SUCC_STATS = StatsStore("succ_stats.json")

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
# IMAGE DOWNLOAD + CONVERT
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
# IMPORTANT: your discord.py build can't edit attachments with Message.edit(files=...).
# So we:
# 1) Edit the original message to update the button label (count)
# 2) Send a NEW message that contains the FULL embed (text+count) + the NEW spoiler image
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
        PLAP_STATS.record_action(actor_id=interaction.user.id, target_id=self.original_actor.id, is_back=True)

        line = random.choice(PLAP_LINES_INTIMATE_NATURAL).format(
            actor=interaction.user.mention,
            target=self.original_actor.mention,
        )
        summary = plap_summary(interaction.user, self.original_actor, self.count)

        # This is the FULL embed you want (text + count + image)
        full_embed = discord.Embed(
            description=f"{line}\n\n**{summary}**",
            color=discord.Color.from_rgb(173, 216, 230),
        )
        full_embed.set_author(
            name=f"{interaction.user.display_name} plaps back",
            icon_url=interaction.user.display_avatar.url,
        )
        full_embed.set_image(url="attachment://action.jpg")

        # Update the button label on the original message so the counter is visible there too
        button.label = f"Plapped ({self.count})"
        button.disabled = False

        # Edit original message (no new file)
        try:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                view=self,
            )
        except Exception:
            pass

        # Send the FULL embed + NEW spoiler image as a NEW message
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
        SUCC_STATS.record_action(actor_id=interaction.user.id, target_id=self.original_actor.id, is_back=True)

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

    PLAP_STATS.record_action(actor_id=interaction.user.id, target_id=target.id, is_back=False)

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

    SUCC_STATS.record_action(actor_id=interaction.user.id, target_id=target.id, is_back=False)

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

    pl = PLAP_STATS.get_user(user.id)
    su = SUCC_STATS.get_user(user.id)

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
