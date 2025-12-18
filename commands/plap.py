import random
import discord
import logging
from discord import app_commands

from bot.safe_defer import safe_defer
from views.plap_view import PlapBackView
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import PLAP_BASE, PLAP_POSITIVE_SETS
from fetch.pick import pick_image
from images.process import process_image
from db.runtime import STATS_DB
from text.plap_lines import PLAP_LINES_INTIMATE_NATURAL
from text.summaries import plap_summary
from fetch.pick import pick_media

log = logging.getLogger("nyunzi")

def setup(bot: discord.Client):
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
        picked = await pick_media(tags, view.seen, tries=8)
        if not picked:
            await interaction.followup.send("Couldn’t fetch an image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5, site, file, fname = picked
        file, fname = await process_image(image_url, max_attempts=3)

        view.seen.add(md5)
        await STATS_DB.record_action("plap", interaction.user.id, target.id, is_back=False)
        count = await STATS_DB.get_pair_count("plap", interaction.user.id, target.id)
        totals = await STATS_DB.get_user("plap", target.id)
        target_total = int(totals.get("received", 0))

        line = random.choice(PLAP_LINES_INTIMATE_NATURAL).format(actor=interaction.user.mention, target=target.mention)
        summary = plap_summary(interaction.user, target, count, target_total=target_total)

        embed = discord.Embed(
            description=f"{line}\n\n**{summary}**\n\n`source: {site}`",
            color=discord.Color.from_rgb(255, 182, 193),
        )
        embed.set_author(name=f"{interaction.user.display_name} used /plap", icon_url=interaction.user.display_avatar.url)

        if file and fname:
            # For jpg/gif, embed image attachment works.
            # For mp4/webm, embed.set_image won't display the video; better to send link instead.
            if fname.endswith((".mp4", ".webm")):
                msg = await interaction.followup.send(embed=embed, file=file, view=view, wait=True)
            else:
                embed.set_image(url=f"attachment://{fname}")
                msg = await interaction.followup.send(embed=embed, file=file, view=view, wait=True)
        else:
            msg = await interaction.followup.send(content=image_url, embed=embed, view=view, wait=True)

        view.message = msg
