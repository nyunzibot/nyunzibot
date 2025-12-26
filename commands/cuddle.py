from typing import Optional
import random
import discord
from discord import HTTPException
import logging
from discord import app_commands

from bot.safe_defer import safe_defer
from views.cuddle_view import CuddleView
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import CUDDLE_BASE, CUDDLE_POSITIVE_SETS, NEGATIVE_TAGS_SFW
from fetch.pick_safebooru import pick_media_sfw, FetchError, get_error_message, is_video_url
from db.runtime import STATS_DB
from text.cuddle_lines import CUDDLE_LINES
from ui.embeds import build_action_embed

log = logging.getLogger("nyunzi")


def _normalize_extra_tags(extra: str) -> str:
    # collapse whitespace
    return " ".join((extra or "").split()).strip()


def _apply_extra_to_ladder(ladder: list[str], extra: str) -> list[str]:
    extra = _normalize_extra_tags(extra)
    if not extra:
        return ladder
    
    neg_suffix = NEGATIVE_TAGS_SFW.strip()
    
    out: list[str] = []
    for s in ladder:
        s = (s or "").strip()
        if not s:
            continue
        # Strip any existing negative tags from the string
        orig_neg = NEGATIVE_TAGS_SFW.strip()
        if orig_neg and s.endswith(orig_neg):
            base = s[: -len(orig_neg)].rstrip()
        else:
            base = s
        
        # Add extra tags and negative suffix
        out.append(f"{base} {extra} {neg_suffix}".strip())
    return out


async def tag_autocomplete_safebooru(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """
    Autocomplete for extra_tags parameter using Safebooru API.
    Returns tag suggestions based on current input.
    """
    from fetch.tags_safebooru import fetch_tag_suggestions_safebooru
    
    current = current.strip()
    if not current:
        return []
    
    parts = current.split()
    last_word = parts[-1] if parts else ""
    
    if not last_word or len(last_word) < 2:
        return []
    
    return await fetch_tag_suggestions_safebooru(current)


def setup(bot: discord.Client):
    @bot.tree.command(name="cuddle", description="[SFW] Cuddle another user with cute anime images")
    @app_commands.allowed_contexts(dms=True, guilds=True, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=True)
    @app_commands.describe(extra_tags="Extra tags to include (space-separated, Safebooru tags)")
    @app_commands.autocomplete(extra_tags=tag_autocomplete_safebooru)
    async def cuddle(interaction: discord.Interaction, target: discord.User, extra_tags: Optional[str] = None):
        # ACK FIRST (avoid 10062)
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        log.info("[CMD] /cuddle actor=%s target=%s", interaction.user.id, target.id)

        if target.id == interaction.user.id:
            await interaction.followup.send("You can cuddle yourself 🥰 but try cuddling someone else!", ephemeral=True)
            return

        view = CuddleView(interaction.user, target, extra_tags=extra_tags or "")

        async def on_status(msg: str):
            try:
                await interaction.edit_original_response(content=msg)
            except Exception:
                pass

        tags = build_tag_ladder(CUDDLE_BASE, CUDDLE_POSITIVE_SETS, negative_tags=NEGATIVE_TAGS_SFW)
        tags = _apply_extra_to_ladder(tags, extra_tags or "")
        result = await pick_media_sfw(tags, view.seen, tries=8, status_cb=on_status)
        image_url, md5, site, file, fname, error = result
        
        if not image_url or error != FetchError.NONE:
            error_msg = get_error_message(error)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        view.seen.add(md5)
        await STATS_DB.record_action("cuddle", interaction.user.id, target.id, is_back=False)
        count = await STATS_DB.get_pair_count("cuddle", interaction.user.id, target.id)
        totals = await STATS_DB.get_user("cuddle", target.id)
        target_total = int(totals.get("received", 0))

        line = random.choice(CUDDLE_LINES).format(actor=f"**{interaction.user.display_name}**", target=f"**{target.display_name}**")

        embed = build_action_embed(
            action_type="cuddle",
            actor=interaction.user,
            target=target,
            action_line=line,
            pair_count=count,
            target_total=target_total,
            source=site,
            is_back=False,
        )

        try:
            if file and fname:
                # Log size for debugging
                try:
                    size = file.fp.getbuffer().nbytes
                    log.info(f"[CUDDLE] Sending file {fname} ({size} bytes)")
                except:
                    pass

                if fname.endswith((".mp4", ".webm")):
                    msg = await interaction.edit_original_response(content="", embed=embed, attachments=[file], view=view)
                else:
                    embed.set_image(url=f"attachment://{fname}")
                    msg = await interaction.edit_original_response(content="", embed=embed, attachments=[file], view=view)
            else:
                content = image_url
                if is_video_url(image_url):
                     content = f"Video compression failed, falling back to URL\n{image_url}"
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view)
        except HTTPException as e:
            if e.code == 40005:  # Payload Too Large
                log.warning(f"[CUDDLE] File too large for Discord (40005), sending URL instead. Error: {e}")
                msg = await interaction.edit_original_response(content=f"📦 File too large to attach\n{image_url}", embed=embed, attachments=[], view=view)
            else:
                raise

        view.message = msg
