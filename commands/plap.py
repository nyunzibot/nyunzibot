from typing import Optional
import random
import discord
from discord import HTTPException
import logging
from discord import app_commands

from bot.safe_defer import safe_defer
from bot.notify import send_dm_notify
from views.plap_view import PlapBackView
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import PLAP_BASE, PLAP_POSITIVE_SETS, NEGATIVE_TAGS, ALLOWED_OVERRIDES, BASE_TAG_OPTIONS
from fetch.pick import pick_media, FetchError, get_error_message, is_video_url
from db.runtime import STATS_DB
from text.plap_lines import PLAP_LINES_INTIMATE_NATURAL
from ui.embeds import build_action_embed

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
        if (t in _NEG_RAW or t in _NEG_WITH_DASH) and t not in ALLOWED_OVERRIDES:
            return "Extra tags cannot include any tag from the negative tag list."
    return None

def _apply_extra_to_ladder(ladder: list[str], extra: str) -> list[str]:
    extra = _normalize_extra_tags(extra)
    if not extra:
        return ladder
    
    # Check if any allowed overrides are in extra tags
    extra_parts = set(extra.split())
    overrides_used = extra_parts & ALLOWED_OVERRIDES
    
    # Separate override tags from regular extra tags
    override_tag = " ".join(overrides_used) if overrides_used else ""
    regular_extras = " ".join(t for t in extra.split() if t not in ALLOWED_OVERRIDES)
    
    neg_suffix = NEGATIVE_TAGS.strip()
    
    # Remove the negative form of any override tags from the negative suffix
    if overrides_used:
        neg_parts = neg_suffix.split()
        neg_parts = [p for p in neg_parts if p.lstrip("-") not in overrides_used]
        neg_suffix = " ".join(neg_parts)
    
    out: list[str] = []
    for s in ladder:
        s = (s or "").strip()
        if not s:
            continue
        # Strip any existing negative tags from the string
        orig_neg = NEGATIVE_TAGS.strip()
        if orig_neg and s.endswith(orig_neg):
            base = s[: -len(orig_neg)].rstrip()
        else:
            base = s
        
        # If override tag is used, replace the base tag with it
        if override_tag:
            # base contains "PLAP_BASE positive_tag", we want to replace PLAP_BASE
            base_parts = base.split()
            if base_parts:
                # Replace first tag (the base) with override tag
                base_parts[0] = override_tag
                base = " ".join(base_parts)
        
        # Add regular extras and negative suffix
        if regular_extras:
            out.append(f"{base} {regular_extras} {neg_suffix}".strip())
        else:
            out.append(f"{base} {neg_suffix}".strip())
    return out

from fetch.tags import fetch_tag_suggestions

async def tag_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """
    Autocomplete for extra_tags parameter.
    1. If current is empty/short, show base options.
    2. If typing, hit API for suggestions.
    """
    current = current.strip()
    
    # If starting a new tag or empty, suggest base options
    # Logic: if ends with space, we are ready for new tag.
    # But current passed by discord usually includes the partial word.
    
    # Check if we are typing a new word or editing an existing one
    parts = current.split()
    last_word = parts[-1] if parts else ""
    
    # If very short or empty, show defaults (filtered by last word)
    if not last_word or len(last_word) < 2:
        # Defaults
        base_prefix = " ".join(parts[:-1])
        choices = []
        for opt in BASE_TAG_OPTIONS:
             if last_word.lower() in opt.lower():
                 val = f"{base_prefix} {opt}".strip()
                 choices.append(app_commands.Choice(name=val, value=val))
        return choices[:25]

    # Else, fetch from API
    return await fetch_tag_suggestions(current)

def setup(bot: discord.Client):
    @bot.tree.command(name="plap", description="Plap another user (DM only)")
    @app_commands.allowed_contexts(dms=True, guilds=False, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=False)
    @app_commands.describe(extra_tags="Extra tags to include (space-separated)")
    @app_commands.autocomplete(extra_tags=tag_autocomplete)
    async def plap(interaction: discord.Interaction, target: discord.User, extra_tags: Optional[str] = None):
        # ACK FIRST (avoid 10062)
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        log.info("[CMD] /plap actor=%s target=%s", interaction.user.id, target.id)

        if target.id == interaction.user.id:
            await interaction.followup.send("Not yourself 😅", ephemeral=True)
            return

        err = _validate_extra_tags(extra_tags or "")
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        view = PlapBackView(interaction.user, target, extra_tags=extra_tags or "")

        async def on_status(msg: str):
            try:
                await interaction.edit_original_response(content=msg)
            except Exception:
                pass

        tags = build_tag_ladder(PLAP_BASE, PLAP_POSITIVE_SETS)
        tags = _apply_extra_to_ladder(tags, extra_tags or "")
        result = await pick_media(tags, view.seen, tries=8, status_cb=on_status)
        image_url, md5, site, file, fname, error = result
        
        if not image_url or error != FetchError.NONE:
            error_msg = get_error_message(error)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        view.seen.add(md5)
        await STATS_DB.record_action("plap", interaction.user.id, target.id, is_back=False)
        count = await STATS_DB.get_pair_count("plap", interaction.user.id, target.id)
        totals = await STATS_DB.get_user("plap", target.id)
        target_total = int(totals.get("received", 0))

        line = random.choice(PLAP_LINES_INTIMATE_NATURAL).format(actor=f"**{interaction.user.display_name}**", target=f"**{target.display_name}**")

        embed = build_action_embed(
            action_type="plap",
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
                    log.info(f"[PLAP] Sending file {fname} ({size} bytes)")
                except:
                    pass

                # For mp4/webm, embed.set_image won't display the video; better to send link instead? 
                # Actually we attach the file.
                if fname.endswith((".mp4", ".webm")):
                    msg = await interaction.edit_original_response(content="", embed=embed, attachments=[file], view=view)
                else:
                    embed.set_image(url=f"attachment://{fname}")
                    msg = await interaction.edit_original_response(content="", embed=embed, attachments=[file], view=view)
            else:
                content = image_url
                # Check for video compression fallback (no file but successful fetch)
                if is_video_url(image_url):
                     content = f"Video compression failed, falling back to URL\n{image_url}"
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view)
        except HTTPException as e:
            if e.code == 40005:  # Payload Too Large
                log.warning(f"[PLAP] File too large for Discord (40005), sending URL instead. Error: {e}")
                msg = await interaction.edit_original_response(content=f"📦 File too large to attach\n{image_url}", embed=embed, attachments=[], view=view)
            else:
                raise

        view.message = msg

        # DM notify target for better mobile notifications (best-effort)
        #await send_dm_notify("plap", interaction.user, target)
