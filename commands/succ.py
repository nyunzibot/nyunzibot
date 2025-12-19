from typing import Optional
import random
import discord
import logging
from discord import app_commands

from bot.safe_defer import safe_defer
from bot.notify import send_dm_notify
from views.succ_view import SuccBackView
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import SUCC_BASE, SUCC_POSITIVE_SETS, NEGATIVE_TAGS
from fetch.pick import pick_image
from images.process import process_image
from db.runtime import STATS_DB
from text.succ_lines import SUCC_LINES_INTIMATE
from text.summaries import succ_summary
from fetch.pick import pick_media

log = logging.getLogger("nyunzi")

# =========================
# EXTRA TAGS (user-supplied)
# =========================
_NEG_WITH_DASH = set(NEGATIVE_TAGS.split())
_NEG_RAW = {t.lstrip("-") for t in _NEG_WITH_DASH}

def _normalize_extra_tags(extra: str) -> str:
    # collapse whitespace
    return " ".join((extra or "").split()).strip()

def _validate_extra_tags(extra: str) -> Optional[str]:
    """Return error message if invalid, else None."""
    extra = _normalize_extra_tags(extra)
    if not extra:
        return None
    parts = extra.split()
    for t in parts:
        if not t:
            continue
        if t.startswith("-"):
            return "Extra tags cannot include negative tags (no leading '-')."
        if t in _NEG_RAW or t in _NEG_WITH_DASH:
            return "Extra tags cannot include any tag from the negative tag list."
    return None

def _apply_extra_to_ladder(ladder: list[str], extra: str) -> list[str]:
    extra = _normalize_extra_tags(extra)
    if not extra:
        return ladder
    neg_suffix = NEGATIVE_TAGS.strip()
    out: list[str] = []
    for s in ladder:
        s = (s or "").strip()
        if not s:
            continue
        if neg_suffix and s.endswith(neg_suffix):
            base = s[: -len(neg_suffix)].rstrip()
            out.append(f"{base} {extra} {neg_suffix}".strip())
        else:
            out.append(f"{s} {extra}".strip())
    return out

def setup(bot: discord.Client):
    @bot.tree.command(name="succ", description="Succ another user (DM only)")
    @app_commands.allowed_contexts(dms=True, guilds=False, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=False)
    @app_commands.describe(extra_tags="Extra tags to include (space-separated)")
    async def succ(interaction: discord.Interaction, target: discord.User, extra_tags: Optional[str] = None):
        # ACK FIRST (avoid 10062)
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        log.info("[CMD] /succ actor=%s target=%s", interaction.user.id, target.id)

        if target.id == interaction.user.id:
            await interaction.followup.send("Not yourself 😅", ephemeral=True)
            return

        err = _validate_extra_tags(extra_tags or "")
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        view = SuccBackView(interaction.user, target, extra_tags=extra_tags or "")

        tags = build_tag_ladder(SUCC_BASE, SUCC_POSITIVE_SETS)
        tags = _apply_extra_to_ladder(tags, extra_tags or "")
        picked = await pick_media(tags, view.seen, tries=8)
        if not picked:
            await interaction.followup.send("Couldn’t fetch an image right now 😭 Try again.", ephemeral=True)
            return

        image_url, md5, site, file, fname = picked
        file, fname = await process_image(image_url, max_attempts=3)

        view.seen.add(md5)
        await STATS_DB.record_action("succ", interaction.user.id, target.id, is_back=False)
        count = await STATS_DB.get_pair_count("succ", interaction.user.id, target.id)

        line = random.choice(SUCC_LINES_INTIMATE).format(actor=f"**{interaction.user.display_name}**", target=f"**{target.display_name}**")
        summary = succ_summary(interaction.user, target, count)

        embed = discord.Embed(
            description=f"{line}\n\n{summary}",
            color=discord.Color(0xFFA6C9),
        )
        embed.set_footer(text=f"source: {site}")
        embed.set_author(name=f"{interaction.user.display_name} used /succ", icon_url=interaction.user.display_avatar.url)

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

        # DM notify target for better mobile notifications (best-effort)
        # await send_dm_notify("succ", interaction.user, target)
