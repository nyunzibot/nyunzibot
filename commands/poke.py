from typing import Optional
import random
import discord
from discord import HTTPException
import logging
from discord import app_commands

from bot.safe_defer import safe_defer
from views.poke_view import PokeView
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import POKE_BASE, POKE_POSITIVE_SETS, NEGATIVE_TAGS_SFW
from fetch.pick_safebooru import pick_media_sfw, FetchError, get_error_message, is_video_url
from db.runtime import STATS_DB
from text.poke_lines import POKE_LINES
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
    @bot.tree.command(name="poke", description="[SFW] Poke another user with cute anime images")
    @app_commands.allowed_contexts(dms=True, guilds=True, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=True)
    @app_commands.describe(extra_tags="Extra tags to include (space-separated)")
    @app_commands.autocomplete(extra_tags=tag_autocomplete_sfw)
    async def poke(interaction: discord.Interaction, target: discord.User, extra_tags: Optional[str] = None):
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        log.info("[CMD] /poke actor=%s target=%s", interaction.user.id, target.id)

        if target.id == interaction.user.id:
            await interaction.followup.send("You poke yourself... why? 👉", ephemeral=True)
            return

        view = PokeView(interaction.user, target, extra_tags=extra_tags or "")

        async def on_status(msg: str):
            try:
                await interaction.edit_original_response(content=msg, allowed_mentions=discord.AllowedMentions.none())
            except Exception:
                pass

        tags = build_tag_ladder(POKE_BASE, POKE_POSITIVE_SETS, negative_tags=NEGATIVE_TAGS_SFW)
        tags = _apply_extra_to_ladder(tags, extra_tags or "")
        result = await pick_media_sfw(tags, view.seen, tries=8, status_cb=on_status, category="poke")
        image_url, md5, site, file, fname, error = result
        
        if not image_url or error != FetchError.NONE:
            error_msg = get_error_message(error)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        view.seen.add(md5)
        await STATS_DB.record_action("poke", interaction.user.id, target.id, is_back=False)
        count = await STATS_DB.get_pair_count("poke", interaction.user.id, target.id)
        totals = await STATS_DB.get_user("poke", target.id)
        target_total = int(totals.get("received", 0))

        line = random.choice(POKE_LINES).format(actor=f"**{interaction.user.display_name}**", target=f"**{target.display_name}**")

        # Always put text in embed
        embed_line = line
        msg_content = ""

        embed = build_action_embed(
            action_type="poke",
            actor=interaction.user,
            target=target,
            action_line=embed_line,
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
                    msg = await interaction.edit_original_response(content=msg_content, embed=embed, attachments=[file], view=view, allowed_mentions=discord.AllowedMentions.none())
                else:
                    embed.set_image(url=f"attachment://{fname}")
                    msg = await interaction.edit_original_response(content=msg_content, embed=embed, attachments=[file], view=view, allowed_mentions=discord.AllowedMentions.none())
            else:
                if isinstance(image_url, list):
                    content = ""
                    embed.set_image(url=image_url[0])
                    embed.description = str(embed.description or "") + f"\n\n[Direct Media Link]({image_url[0]})"
                else:
                    if is_video_url(image_url):
                        content = f"Video compression failed, falling back to URL\n{image_url}"
                    else:
                        content = ""
                        embed.set_image(url=image_url)
                        embed.description = str(embed.description or "") + f"\n\n[Direct Media Link]({image_url})"
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
        except HTTPException as e:
            if e.code == 40005:
                log.warning(f"[POKE] File too large for Discord (40005), sending URL instead.")
                url_content = "\n".join(image_url) if isinstance(image_url, list) else image_url
                content = "📦 File too large to attach"
                if is_video_url(url_content):
                    content += f"\n{url_content}"
                else:
                    embed.set_image(url=url_content)
                msg = await interaction.edit_original_response(content=content, embed=embed, attachments=[], view=view, allowed_mentions=discord.AllowedMentions.none())
            else:
                raise

        view.message = msg
