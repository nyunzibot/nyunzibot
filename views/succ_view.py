import random
import discord
import logging

from bot.safe_defer import safe_defer
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import SUCC_BASE, SUCC_POSITIVE_SETS
from fetch.pick import pick_image
from images.process import process_image
from db.stats import InteractionSeen
from db.runtime import STATS_DB
from text.succ_lines import SUCC_LINES_INTIMATE
from text.summaries import succ_summary

log = logging.getLogger("nyunzi")

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

        # CHANGED: process_media returns (file, fname)
        file, fname = await process_image(image_url, max_attempts=3)
        if not file or not fname:
            await interaction.followup.send("Media failed 😭 (download/convert)", ephemeral=True)
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

        # CHANGED: only set embed image for image/gif attachments
        if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            embed.set_image(url=f"attachment://{fname}")

        try:
            # CHANGED: attachments=[file] where file is discord.File
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=embed,
                attachments=[file],
                view=self
            )
        except Exception:
            # CHANGED: for video, send as link; otherwise attach
            if fname.lower().endswith((".mp4", ".webm")):
                await interaction.followup.send(content=image_url, embed=embed, view=self)
            else:
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

        # CHANGED: process_media returns (file, fname)
        file, fname = await process_image(image_url, max_attempts=3)
        if not file or not fname:
            await interaction.followup.send("Media failed 😭 (download/convert)", ephemeral=True)
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

        # CHANGED: only set embed image for image/gif attachments
        if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            full_embed.set_image(url=f"attachment://{fname}")

        button.label = f"Succ’d ({self.count})"
        try:
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            self.message = interaction.message
        except Exception:
            pass

        # CHANGED: for video, send as link; otherwise attach
        if fname.lower().endswith((".mp4", ".webm")):
            await interaction.followup.send(content=image_url, embed=full_embed)
        else:
            await interaction.followup.send(embed=full_embed, file=file)
