import random
import discord
import logging
import asyncio

from bot.safe_defer import safe_defer
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import BOUNCE_BASE, BOUNCE_POSITIVE_SETS, NEGATIVE_TAGS
from fetch.pick import pick_image
from images.process import process_image
from db.stats import InteractionSeen
from db.runtime import STATS_DB
from text.bounce_lines import BOUNCE_LINES
from text.summaries import bounce_summary

log = logging.getLogger("nyunzi")

class BounceView(discord.ui.View):
    def __init__(self, original_actor: discord.User, original_target: discord.User, extra_tags: str = ""):
        super().__init__(timeout=3600)
        self.original_actor = original_actor
        self.original_target = original_target
        self.extra_tags = " ".join((extra_tags or "").split()).strip()
        self.count = 1
        self.message: discord.Message | None = None
        self.seen = InteractionSeen(original_actor.id, original_target.id)
        self.rerolls_left = 3

    def _apply_extra_to_ladder(self, ladder: list[str]) -> list[str]:
        """Inject extra tags before NEGATIVE_TAGS suffix."""
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

        remaining = self.rerolls_left
        if remaining <= 0:
            await interaction.followup.send("No rerolls left for this message 😤", ephemeral=True)
            return

        # Loading animation
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

        tags = self._apply_extra_to_ladder(build_tag_ladder(BOUNCE_BASE, BOUNCE_POSITIVE_SETS))
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

        line = random.choice(BOUNCE_LINES).format(
            actor=f"**{self.original_actor.display_name}**",
            target=f"**{self.original_target.display_name}**"
        )
        count = await STATS_DB.get_pair_count("bounce", self.original_actor.id, self.original_target.id)
        # Note: We aren't calculating target_total generally for refresh unless we want to, 
        # but plap_view did it. Let's do it if logic permits, but plap_view reroll 
        # calls get_user("plap", target.id). We'll assume "bounce" stats.
        totals = await STATS_DB.get_user("bounce", self.original_target.id)
        target_total = int(totals.get("received", 0))
        
        summary = bounce_summary(self.original_actor, self.original_target, count) # simplified arguments for bounce_summary?
        # Wait, I defined bounce_summary to take 3 args (actor, target, count). 
        # plap_summary takes target_total as optional. I didn't add target_total to bounce_summary.
        # I will update bounce_summary logic if I want to use target_total, but for now I'll stick to 3.

        embed = discord.Embed(
            description=f"{line}\n\n{summary}\n\n`source: {site}`",
            color=discord.Color(0xFF9E80),
        )
        embed.set_author(name=f"{self.original_actor.display_name} used /bounce", icon_url=self.original_actor.display_avatar.url)

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
