import random
import discord
import logging
from discord import app_commands

from bot.safe_defer import safe_defer
from views.succ_view import SuccBackView
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import SUCC_BASE, SUCC_POSITIVE_SETS
from fetch.pick import pick_image
from images.process import process_image
from db.runtime import STATS_DB
from text.succ_lines import SUCC_LINES_INTIMATE
from text.summaries import succ_summary

log = logging.getLogger("nyunzi")

def setup(bot: discord.Client):
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
