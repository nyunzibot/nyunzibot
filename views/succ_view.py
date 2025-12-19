import random
import discord
import logging
import asyncio  # ✅ added

from bot.safe_defer import safe_defer
from bot.notify import send_dm_notify
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

    @discord.ui.button(label="Refresh (3)", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        if interaction.user.id != self.original_actor.id:
            await interaction.followup.send("Only the sender can refresh 🔄", ephemeral=True)
            return

        remaining = getattr(self, "rerolls_left", 3)
        if remaining <= 0:
            await interaction.followup.send("No rerolls left for this message 😤", ephemeral=True)
            return

        # ✅ loading animation (DM-safe): edit view label
        button.disabled = True
        button.label = "Loading."
        try:
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
        except Exception:
            pass

        try:
            await asyncio.sleep(0.6)
            button.label = "Loading.."
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)

            await asyncio.sleep(0.6)
            button.label = "Loading..."
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
        except Exception:
            pass

        tags = build_tag_ladder(SUCC_BASE, SUCC_POSITIVE_SETS)
        picked = await pick_image(tags, self.seen)
        if not picked:
            button.disabled = False
            button.label = f"Refresh ({remaining})"
            try:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            except Exception:
                pass
            await interaction.followup.send("Couldn’t fetch a new image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5, site = picked

        file, fname = await process_image(image_url, max_attempts=3)
        if not file or not fname:
            button.disabled = False
            button.label = f"Refresh ({remaining})"
            try:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            except Exception:
                pass
            await interaction.followup.send("Media failed 😭 (download/convert)", ephemeral=True)
            return

        self.seen.add(md5)
        self.rerolls_left = remaining - 1
        button.disabled = False
        button.label = f"Refresh ({self.rerolls_left})"

        line = random.choice(SUCC_LINES_INTIMATE).format(
            actor=self.original_actor.mention,
            target=self.original_target.mention
        )
        count = await STATS_DB.get_pair_count("succ", self.original_actor.id, self.original_target.id)
        summary = succ_summary(self.original_actor, self.original_target, count)

        embed = discord.Embed(
            description=f"{line}\n\n**{summary}**\n\n`source: {site}`",
            color=discord.Color.from_rgb(199, 21, 133),
        )
        embed.set_author(
            name=f"{self.original_actor.display_name} used /succ",
            icon_url=self.original_actor.display_avatar.url
        )

        if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            embed.set_image(url=f"attachment://{fname}")

        try:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=embed,
                attachments=[file],
                view=self
            )
        except Exception:
            if fname.lower().endswith((".mp4", ".webm")):
                await interaction.followup.send(embed=embed, file=file, view=self, wait=True)
            else:
                await interaction.followup.send(embed=embed, file=file, view=self)

    @discord.ui.button(label="Succ back", emoji="🫦", style=discord.ButtonStyle.danger)
    async def succ_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ✅ gate FIRST (before defer)
        if interaction.user.id != self.original_target.id:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("Not for you 😤", ephemeral=True)
                else:
                    await interaction.response.send_message("Not for you 😤", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("Not for you 😤", ephemeral=True)
            return

        # ✅ now it's safe to defer
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(thinking=True)
        except Exception:
            return

        tags = build_tag_ladder(SUCC_BASE, SUCC_POSITIVE_SETS)
        picked = await pick_image(tags, self.seen)
        if not picked:
            await interaction.followup.send("Couldn’t fetch a new image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5, site = picked

        file, fname = await process_image(image_url, max_attempts=3)
        if not file or not fname:
            await interaction.followup.send("Media failed 😭 (download/convert)", ephemeral=True)
            return

        self.seen.add(md5)
        await STATS_DB.record_action("succ", interaction.user.id, self.original_actor.id, is_back=True)
        count = await STATS_DB.get_pair_count("succ", interaction.user.id, self.original_actor.id)
        self.count = count

        line = random.choice(SUCC_LINES_INTIMATE).format(
            actor=interaction.user.mention,
            target=self.original_actor.mention
        )
        summary = succ_summary(interaction.user, self.original_actor, count)

        full_embed = discord.Embed(
            description=f"{line}\n\n**{summary}**\n\n`source: {site}`",
            color=discord.Color.from_rgb(255, 105, 180),
        )
        full_embed.set_author(
            name=f"{interaction.user.display_name} succs back",
            icon_url=interaction.user.display_avatar.url
        )

        if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            full_embed.set_image(url=f"attachment://{fname}")

        new_view = SuccBackView(interaction.user, self.original_actor)
        new_view.seen = self.seen
        new_view.count = self.count

        try:
            msg = await interaction.edit_original_response(
                embed=full_embed,
                view=new_view,
                files=[file],
            )
            new_view.message = msg
            # await send_dm_notify("succ", interaction.user, self.original_actor)
        except TypeError:
            try:
                msg = await interaction.edit_original_response(
                    embed=full_embed,
                    view=new_view,
                    attachments=[file],
                )
                new_view.message = msg
                # await send_dm_notify("succ", interaction.user, self.original_actor)
            except Exception:
                msg = await interaction.followup.send(embed=full_embed, file=file, view=new_view, wait=True)
                new_view.message = msg
