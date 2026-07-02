import random
import urllib.parse
import discord
from discord import HTTPException
import logging
import asyncio

from bot.safe_defer import safe_defer
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import KISS_BASE, KISS_POSITIVE_SETS, NEGATIVE_TAGS_SFW
from fetch.pick_safebooru import pick_media_sfw, FetchError, get_error_message, is_video_url
from db.stats import InteractionSeen
from db.runtime import STATS_DB
from text.kiss_lines import KISS_LINES, KISS_EMOTES
from ui.embeds import build_action_embed, build_multi_image_embeds

log = logging.getLogger("nyunzi")


class KissView(discord.ui.View):
    def __init__(self, original_actor: discord.User, original_target: discord.User, extra_tags: str = ""):
        super().__init__(timeout=None)
        self.original_actor = original_actor
        self.original_target = original_target
        self.extra_tags = " ".join((extra_tags or "").split()).strip()
        self.message: discord.Message | None = None
        self.seen = InteractionSeen(original_actor.id, original_target.id)
        self.rerolls_left = 3

        safe_tags = urllib.parse.quote(self.extra_tags.replace(':', '_'))[:40] if hasattr(self, 'extra_tags') and self.extra_tags else "0"
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.label and "Refresh" in child.label:
                    child.custom_id = f"act:kiss:reroll:{self.original_actor.id}:{self.original_target.id}:{safe_tags}"
                elif child.label and "back" in child.label.lower():
                    child.custom_id = f"act:kiss:back:{self.original_actor.id}:{self.original_target.id}:{safe_tags}"

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

        tags = self._apply_extra_to_ladder(build_tag_ladder(KISS_BASE, KISS_POSITIVE_SETS, negative_tags=NEGATIVE_TAGS_SFW))
        result = await pick_media_sfw(tags, self.seen, tries=8, category="kiss")
        image_url, md5, site, file, fname, error = result

        if not image_url or error != FetchError.NONE:
            button.disabled = False
            button.label = f"Refresh ({remaining})"
            try:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            except Exception:
                pass
            error_msg = get_error_message(error)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        self.rerolls_left = remaining - 1
        button.disabled = False
        button.label = f"Refresh ({self.rerolls_left})"

        line = random.choice(KISS_LINES).format(
            actor=f"**{self.original_actor.display_name}**",
            target=f"**{self.original_target.display_name}**",
            emote=random.choice(KISS_EMOTES)
        )
        count = await STATS_DB.get_pair_count("kiss", self.original_actor.id, self.original_target.id)
        totals = await STATS_DB.get_user("kiss", self.original_target.id)
        target_total = int(totals.get("received", 0))

        embed = build_action_embed(
            action_type="kiss",
            actor=self.original_actor,
            target=self.original_target,
            action_line=line,
            pair_count=count,
            target_total=target_total,
            source=site,
            is_back=False,
        )

        try:
            # Handle multi-image case
            if isinstance(file, list) and isinstance(fname, list) and file:
                embeds = build_multi_image_embeds(embed, fname)
                await interaction.followup.edit_message(
                    message_id=interaction.message.id,
                    embeds=embeds,
                    attachments=file,
                    view=self
                )
            elif file and fname:
                if fname.lower().endswith((".mp4", ".webm")):
                    await interaction.followup.edit_message(
                        message_id=interaction.message.id,
                        embed=embed,
                        attachments=[file],
                        view=self
                    )
                else:
                    embed.set_image(url=f"attachment://{fname}")
                    await interaction.followup.edit_message(
                        message_id=interaction.message.id,
                        embed=embed,
                        attachments=[file],
                        view=self
                    )
            else:
                 # Fallback URL
                content = "\n".join(image_url) if isinstance(image_url, list) else image_url
                if is_video_url(content):
                     content = f"Video compression failed, falling back to URL\n{content}"
                
                await interaction.followup.edit_message(
                    message_id=interaction.message.id,
                    content=content,
                    embed=embed,
                    view=self
                )

        except HTTPException as e:
            if e.code == 40005:
                log.warning("[KISS VIEW] File too large for Discord")
                await interaction.followup.send("📦 File too large to attach. Try refreshing for a different image.", ephemeral=True)
            else:
                 raise
        except Exception:
             # If editing fails, maybe try sending as new if safe? But we want to edit.
             pass

    @discord.ui.button(label="Kiss back", emoji="💋", style=discord.ButtonStyle.primary)
    async def kiss_back(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        button.label = "Kissed"
        try:
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
        except Exception:
            pass

        tags = self._apply_extra_to_ladder(build_tag_ladder(KISS_BASE, KISS_POSITIVE_SETS, negative_tags=NEGATIVE_TAGS_SFW))
        result = await pick_media_sfw(tags, self.seen, tries=8, category="kiss")
        image_url, md5, site, file, fname, error = result

        if not image_url or error != FetchError.NONE:
            button.disabled = False
            button.label = "Kiss back"
            try:
                await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
            except Exception:
                pass
            error_msg = get_error_message(error)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        await STATS_DB.record_action("kiss", interaction.user.id, self.original_actor.id, is_back=True)
        count = await STATS_DB.get_pair_count("kiss", interaction.user.id, self.original_actor.id)
        totals = await STATS_DB.get_user("kiss", self.original_actor.id)
        target_total = int(totals.get("received", 0))

        line = random.choice(KISS_LINES).format(
            actor=f"**{interaction.user.display_name}**",
            target=f"**{self.original_actor.display_name}**",
            emote=random.choice(KISS_EMOTES)
        )

        full_embed = build_action_embed(
            action_type="kiss",
            actor=interaction.user,
            target=self.original_actor,
            action_line=line,
            pair_count=count,
            target_total=target_total,
            source=site,
            is_back=True,
        )

        new_view = KissView(interaction.user, self.original_actor, extra_tags=self.extra_tags)
        new_view.seen = self.seen

        for item in new_view.children:
            if isinstance(item, discord.ui.Button) and item.label == "Kiss back":
                item.label = "Kiss again"

        try:
            # Handle multi-image case
            if isinstance(file, list) and isinstance(fname, list) and file:
                embeds = build_multi_image_embeds(full_embed, fname)
                msg = await interaction.edit_original_response(embeds=embeds, attachments=file, view=new_view)
                new_view.message = msg
            elif file and fname:
                if fname.lower().endswith((".mp4", ".webm")):
                    msg = await interaction.edit_original_response(embed=full_embed, attachments=[file], view=new_view)
                    new_view.message = msg
                else:
                    full_embed.set_image(url=f"attachment://{fname}")
                    msg = await interaction.edit_original_response(embed=full_embed, attachments=[file], view=new_view)
                    new_view.message = msg
            else:
                 # Fallback URL
                content = "\n".join(image_url) if isinstance(image_url, list) else image_url
                if is_video_url(content):
                     content = f"Video compression failed, falling back to URL\n{content}"
                
                msg = await interaction.edit_original_response(content=content, embed=full_embed, view=new_view)
                new_view.message = msg

        except HTTPException as e:
            if e.code == 40005:
                await interaction.followup.send("📦 File too large. Try again.", ephemeral=True)
            else:
                raise
        except TypeError:
             pass

