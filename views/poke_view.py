import random
import discord
from discord import HTTPException
import logging
import asyncio

from bot.safe_defer import safe_defer
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import POKE_BASE, POKE_POSITIVE_SETS, NEGATIVE_TAGS_SFW
from fetch.pick_safebooru import pick_image_sfw, FetchError, get_error_message
from images.process import process_image, ProcessError
from db.stats import InteractionSeen
from db.runtime import STATS_DB
from text.poke_lines import POKE_LINES
from ui.embeds import build_action_embed

log = logging.getLogger("nyunzi")


class PokeView(discord.ui.View):
    def __init__(self, original_actor: discord.User, original_target: discord.User, extra_tags: str = ""):
        super().__init__(timeout=3600)
        self.original_actor = original_actor
        self.original_target = original_target
        self.extra_tags = " ".join((extra_tags or "").split()).strip()
        self.message: discord.Message | None = None
        self.seen = InteractionSeen(original_actor.id, original_target.id)
        self.rerolls_left = 3

    def _apply_extra_to_ladder(self, ladder: list[str]) -> list[str]:
        if not self.extra_tags:
            return ladder
        neg_suffix = (NEGATIVE_TAGS_SFW or "").strip()
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

        if interaction.user.id != self.original_actor.id:
            await interaction.followup.send("Only the sender can refresh 🔄", ephemeral=True)
            return

        remaining = self.rerolls_left
        if remaining <= 0:
            await interaction.followup.send("No rerolls left for this message 😤", ephemeral=True)
            return

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

        tags = self._apply_extra_to_ladder(build_tag_ladder(POKE_BASE, POKE_POSITIVE_SETS, negative_tags=NEGATIVE_TAGS_SFW))
        picked, fetch_error = await pick_image_sfw(tags, self.seen, category="poke")
        if not picked:
            button.disabled = False
            button.label = f"Refresh ({remaining})"
            try:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            except Exception:
                pass
            error_msg = get_error_message(fetch_error)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        image_url, md5, site = picked
        file, fname, process_error = await process_image(image_url, max_attempts=3, spoiler=False)
        if not file or not fname:
            button.disabled = False
            button.label = f"Refresh ({remaining})"
            try:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            except Exception:
                pass
            if process_error == ProcessError.RATE_LIMITED:
                error_msg = get_error_message(FetchError.RATE_LIMITED)
            elif process_error == ProcessError.FILE_TOO_LARGE:
                error_msg = get_error_message(FetchError.FILE_TOO_LARGE)
            else:
                error_msg = get_error_message(FetchError.PROCESSING_FAILED)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        self.seen.add(md5)
        self.rerolls_left = remaining - 1
        button.disabled = False
        button.label = f"Refresh ({self.rerolls_left})"

        line = random.choice(POKE_LINES).format(
            actor=f"**{self.original_actor.display_name}**",
            target=f"**{self.original_target.display_name}**"
        )
        count = await STATS_DB.get_pair_count("poke", self.original_actor.id, self.original_target.id)
        totals = await STATS_DB.get_user("poke", self.original_target.id)
        target_total = int(totals.get("received", 0))

        embed = build_action_embed(
            action_type="poke",
            actor=self.original_actor,
            target=self.original_target,
            action_line=line,
            pair_count=count,
            target_total=target_total,
            source=site,
            is_back=False,
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
        except HTTPException as e:
            if e.code == 40005:
                log.warning("[POKE VIEW] File too large for Discord")
                await interaction.followup.send("📦 File too large to attach. Try refreshing.", ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, file=file, view=self)
        except Exception:
            await interaction.followup.send(embed=embed, file=file, view=self)

    @discord.ui.button(label="Poke back", emoji="👉", style=discord.ButtonStyle.primary)
    async def poke_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.original_target.id:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("Not for you 😤", ephemeral=True)
                else:
                    await interaction.response.send_message("Not for you 😤", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("Not for you 😤", ephemeral=True)
            return

        try:
            if not interaction.response.is_done():
                await interaction.response.defer(thinking=True)
        except Exception:
            return

        button.disabled = True
        button.label = "Poked"
        try:
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
        except Exception:
            pass

        tags = self._apply_extra_to_ladder(build_tag_ladder(POKE_BASE, POKE_POSITIVE_SETS, negative_tags=NEGATIVE_TAGS_SFW))
        picked, fetch_error = await pick_image_sfw(tags, self.seen, category="poke")
        if not picked:
            button.disabled = False
            button.label = "Poke back"
            try:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            except Exception:
                pass
            error_msg = get_error_message(fetch_error)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        image_url, md5, site = picked
        file, fname, process_error = await process_image(image_url, max_attempts=3, spoiler=False)
        if not file or not fname:
            button.disabled = False
            button.label = "Poke back"
            try:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            except Exception:
                pass
            if process_error == ProcessError.RATE_LIMITED:
                error_msg = get_error_message(FetchError.RATE_LIMITED)
            elif process_error == ProcessError.FILE_TOO_LARGE:
                error_msg = get_error_message(FetchError.FILE_TOO_LARGE)
            else:
                error_msg = get_error_message(FetchError.PROCESSING_FAILED)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        self.seen.add(md5)
        await STATS_DB.record_action("poke", interaction.user.id, self.original_actor.id, is_back=True)
        count = await STATS_DB.get_pair_count("poke", interaction.user.id, self.original_actor.id)
        totals = await STATS_DB.get_user("poke", self.original_actor.id)
        target_total = int(totals.get("received", 0))

        line = random.choice(POKE_LINES).format(
            actor=f"**{interaction.user.display_name}**",
            target=f"**{self.original_actor.display_name}**"
        )

        full_embed = build_action_embed(
            action_type="poke",
            actor=interaction.user,
            target=self.original_actor,
            action_line=line,
            pair_count=count,
            target_total=target_total,
            source=site,
            is_back=True,
        )

        if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            full_embed.set_image(url=f"attachment://{fname}")

        new_view = PokeView(interaction.user, self.original_actor, extra_tags=self.extra_tags)
        new_view.seen = self.seen

        for item in new_view.children:
            if isinstance(item, discord.ui.Button) and item.label == "Poke back":
                item.label = "Poke again"

        try:
            msg = await interaction.edit_original_response(embed=full_embed, view=new_view, attachments=[file])
            new_view.message = msg
        except HTTPException as e:
            if e.code == 40005:
                await interaction.followup.send("📦 File too large. Try again.", ephemeral=True)
            else:
                raise
        except TypeError:
            try:
                msg = await interaction.edit_original_response(embed=full_embed, view=new_view, attachments=[file])
                new_view.message = msg
            except Exception:
                msg = await interaction.followup.send(embed=full_embed, file=file, view=new_view, wait=True)
                new_view.message = msg
