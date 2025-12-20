import random
import discord
import logging
import asyncio  # ✅ added

from bot.safe_defer import safe_defer
from bot.notify import send_dm_notify
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import PLAP_BASE, PLAP_POSITIVE_SETS, NEGATIVE_TAGS
from fetch.pick import pick_image
from images.process import process_image
from db.stats import InteractionSeen
from db.runtime import STATS_DB
from text.plap_lines import PLAP_LINES_INTIMATE_NATURAL
from text.summaries import plap_summary

log = logging.getLogger("nyunzi")

class PlapBackView(discord.ui.View):
    def __init__(self, original_actor: discord.User, original_target: discord.User, extra_tags: str = ""):
        super().__init__(timeout=3600)
        self.original_actor = original_actor
        self.original_target = original_target
        self.extra_tags = " ".join((extra_tags or "").split()).strip()
        self.count = 1
        self.message: discord.Message | None = None
        self.seen = InteractionSeen(original_actor.id, original_target.id)

    def _apply_extra_to_ladder(self, ladder: list[str]) -> list[str]:
        """Inject extra tags before NEGATIVE_TAGS suffix (validated at command entry)."""
        if not self.extra_tags:
            return ladder
        neg_suffix = (NEGATIVE_TAGS or "").strip()
        out: list[str] = []
        for s in ladder:
            s = (s or "").strip()
            if not s:
                continue
            if neg_suffix and s.endswith(neg_suffix):
                base = s[: -len(neg_suffix)].rstrip()
                out.append(f"{base} {self.extra_tags} {neg_suffix}".strip())
            else:
                out.append(f"{s} {self.extra_tags}".strip())
        return out

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

        # Only the original actor can reroll their own message
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

        tags = self._apply_extra_to_ladder(build_tag_ladder(PLAP_BASE, PLAP_POSITIVE_SETS))
        picked = await pick_image(tags, self.seen)
        if not picked:
            # restore button state
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
            # restore button state
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

        line = random.choice(PLAP_LINES_INTIMATE_NATURAL).format(
            actor=f"**{self.original_actor.display_name}**",
            target=f"**{self.original_target.display_name}**"
        )
        count = await STATS_DB.get_pair_count("plap", self.original_actor.id, self.original_target.id)
        totals = await STATS_DB.get_user("plap", self.original_target.id)
        target_total = int(totals.get("received", 0))
        summary = plap_summary(self.original_actor, self.original_target, count, target_total=target_total)

        embed = discord.Embed(
            description=f"{line}\n\n{summary}\n\n`source: {site}`",
            color=discord.Color(0xFF9E80),
        )
        embed.set_author(name=f"{self.original_actor.display_name} used /plap", icon_url=self.original_actor.display_avatar.url)

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

    @discord.ui.button(label="Plap back", emoji="💢", style=discord.ButtonStyle.primary)
    async def plap_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ✅ gate FIRST (so we don't defer/respond for someone who shouldn't use it)
        if interaction.user.id != self.original_target.id:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("Not for you 😤", ephemeral=True)
                else:
                    await interaction.response.send_message("Not for you 😤", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("Not for you 😤", ephemeral=True)
            return

        # ✅ show thinking bubble (we will turn THIS into the new message)
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(thinking=True)
        except Exception:
            return

        # ✅ FIRST message: "Plap back" -> "Plapped" (disabled)
        button.disabled = True
        button.label = "Plapped"
        try:
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
        except Exception:
            pass

        tags = self._apply_extra_to_ladder(build_tag_ladder(PLAP_BASE, PLAP_POSITIVE_SETS))
        picked = await pick_image(tags, self.seen)
        if not picked:
            # restore button state on failure
            button.disabled = False
            button.label = "Plap back"
            try:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            except Exception:
                pass
            await interaction.followup.send("Couldn’t fetch a new image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5, site = picked

        file, fname = await process_image(image_url, max_attempts=3)
        if not file or not fname:
            # restore button state on failure
            button.disabled = False
            button.label = "Plap back"
            try:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            except Exception:
                pass
            await interaction.followup.send("Media failed 😭 (download/convert)", ephemeral=True)
            return

        self.seen.add(md5)
        await STATS_DB.record_action("plap", interaction.user.id, self.original_actor.id, is_back=True)
        count = await STATS_DB.get_pair_count("plap", interaction.user.id, self.original_actor.id)
        totals = await STATS_DB.get_user("plap", self.original_actor.id)
        target_total = int(totals.get("received", 0))
        self.count = count

        line = random.choice(PLAP_LINES_INTIMATE_NATURAL).format(
            actor=f"**{interaction.user.display_name}**",
            target=f"**{self.original_actor.display_name}**"
        )
        summary = plap_summary(interaction.user, self.original_actor, count, target_total=target_total)

        full_embed = discord.Embed(
            description=f"{line}\n\n{summary}\n\n`source: {site}`",
            color=discord.Color(0xFF9E80),
        )
        full_embed.set_author(name=f"{interaction.user.display_name} plaps back", icon_url=interaction.user.display_avatar.url)

        if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            full_embed.set_image(url=f"attachment://{fname}")

        # ✅ NEW: the "thinking..." message becomes the new message, with a NEW view
        new_view = PlapBackView(interaction.user, self.original_actor, extra_tags=self.extra_tags)
        new_view.seen = self.seen
        new_view.count = self.count

        # ✅ SECOND message: "Plap back" -> "Plap again" (enabled)
        for item in new_view.children:
            if isinstance(item, discord.ui.Button) and item.label == "Plap back":
                item.label = "Plap again"

        try:
            msg = await interaction.edit_original_response(
                embed=full_embed,
                view=new_view,
                files=[file],
            )
            new_view.message = msg

            # DM notify original actor when someone plaps back (best-effort)
            #await send_dm_notify("plap", interaction.user, self.original_actor)
        except TypeError:
            # fallback for versions that don't accept files=
            try:
                msg = await interaction.edit_original_response(
                    embed=full_embed,
                    view=new_view,
                    attachments=[file],
                )
                new_view.message = msg

                # DM notify original actor when someone plaps back (best-effort)
                #await send_dm_notify("plap", interaction.user, self.original_actor)
            except Exception:
                # last resort: keep old message untouched, just send a new one
                msg = await interaction.followup.send(embed=full_embed, file=file, view=new_view, wait=True)
                new_view.message = msg
