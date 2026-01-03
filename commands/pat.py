from typing import Optional
import random
import discord
from discord import HTTPException
import logging
from discord import app_commands

from bot.safe_defer import safe_defer
from views.pat_view import PatView
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import PAT_BASE, PAT_POSITIVE_SETS, NEGATIVE_TAGS_SFW
from fetch.pick_safebooru import pick_media_sfw, FetchError, get_error_message, is_video_url
from db.runtime import STATS_DB
from text.pat_lines import PAT_LINES
from ui.embeds import build_action_embed, build_multi_image_embeds

log = logging.getLogger("nyunzi")


def _normalize_extra_tags(extra: str) -> str:
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
        orig_neg = NEGATIVE_TAGS_SFW.strip()
        if orig_neg and s.endswith(orig_neg):
            base = s[: -len(orig_neg)].rstrip()
        else:
            base = s
        out.append(f"{base} {extra} {neg_suffix}".strip())
    return out


async def tag_autocomplete_sfw(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
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
    @bot.tree.command(name="pat", description="[SFW] Headpat another user with cute anime images")
    @app_commands.allowed_contexts(dms=True, guilds=True, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=True)
    @app_commands.describe(extra_tags="Extra tags to include (space-separated)")
    @app_commands.autocomplete(extra_tags=tag_autocomplete_sfw)
    async def pat(interaction: discord.Interaction, target: discord.User, extra_tags: Optional[str] = None):
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        log.info("[CMD] /pat actor=%s target=%s", interaction.user.id, target.id)

        if target.id == interaction.user.id:
            await interaction.followup.send("You pat yourself on the head! Good job! ✋", ephemeral=True)
            return

        view = PatView(interaction.user, target, extra_tags=extra_tags or "")

        async def on_status(msg: str):
            try:
                await interaction.edit_original_response(content=msg, allowed_mentions=discord.AllowedMentions.none())
            except Exception:
                pass

        tags = build_tag_ladder(PAT_BASE, PAT_POSITIVE_SETS, negative_tags=NEGATIVE_TAGS_SFW)
        tags = _apply_extra_to_ladder(tags, extra_tags or "")
        result = await pick_media_sfw(tags, view.seen, tries=8, status_cb=on_status, category="pat")
        image_url, md5, site, file, fname, error = result
        
        if not image_url or error != FetchError.NONE:
            error_msg = get_error_message(error)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        view.seen.add(md5)
        await STATS_DB.record_action("pat", interaction.user.id, target.id, is_back=False)
        count = await STATS_DB.get_pair_count("pat", interaction.user.id, target.id)
        totals = await STATS_DB.get_user("pat", target.id)
        target_total = int(totals.get("received", 0))

        line = random.choice(PAT_LINES).format(actor=f"**{interaction.user.display_name}**", target=f"**{target.display_name}**")

        embed = build_action_embed(
            action_type="pat",
            actor=interaction.user,
            target=target,
            action_line=line,
            pair_count=count,
            target_total=target_total,
            source=site,
            is_back=False,
        )

        try:
            # Handle multi-image case (file and fname are lists)
            if isinstance(file, list) and isinstance(fname, list) and file:
                embeds = build_multi_image_embeds(embed, fname)
                msg = await interaction.edit_original_response(content="", embeds=embeds, attachments=file, view=view, allowed_mentions=discord.AllowedMentions.none())
            elif file and fname:
                if fname.endswith((".mp4", ".webm")):
                    embed.set_image(url=f"attachment://{fname}")
                    msg = await interaction.edit_original_response(content="", embed=embed, attachments=[file], view=view, allowed_mentions=discord.AllowedMentions.none())
                else:
                    embed.set_image(url=f"attachment://{fname}")
                    msg = await interaction.edit_original_response(content="", embed=embed, attachments=[file], view=view, allowed_mentions=discord.AllowedMentions.none())
            else:
                if isinstance(image_url, list):
                    content = "\n".join(image_url)
                else:
                    content = image_url
                    if is_video_url(image_url):
                        content = f"Video compression failed, falling back to URL\n{image_url}"
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
        except HTTPException as e:
            if e.code == 40005:
                log.warning(f"[PAT] File too large for Discord (40005), sending URL instead.")
                url_content = "\n".join(image_url) if isinstance(image_url, list) else image_url
                msg = await interaction.edit_original_response(content=f"📦 File too large to attach\n{url_content}", embed=embed, attachments=[], view=view, allowed_mentions=discord.AllowedMentions.none())
            else:
                raise

        view.message = msg
