from typing import Optional
import random
import discord
import logging
from discord import app_commands

from bot.safe_defer import safe_defer
from bot.notify import send_dm_notify
from views.succ_view import SuccBackView
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import SUCC_BASE, SUCC_POSITIVE_SETS, NEGATIVE_TAGS, ALLOWED_OVERRIDES, BASE_TAG_OPTIONS
from fetch.pick import pick_media, FetchError, get_error_message
from db.runtime import STATS_DB
from text.succ_lines import SUCC_LINES_INTIMATE
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
            # base contains "SUCC_BASE positive_tag", we want to replace SUCC_BASE
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

async def extra_tags_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete for extra_tags parameter."""
    return [
        app_commands.Choice(name=opt, value=opt)
        for opt in BASE_TAG_OPTIONS if current.lower() in opt.lower()
    ][:25]

def setup(bot: discord.Client):
    @bot.tree.command(name="succ", description="Succ another user (DM only)")
    @app_commands.allowed_contexts(dms=True, guilds=False, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=False)
    @app_commands.describe(extra_tags="Extra tags to include (space-separated)")
    @app_commands.autocomplete(extra_tags=extra_tags_autocomplete)
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
        result = await pick_media(tags, view.seen, tries=8)
        image_url, md5, site, file, fname, error = result
        
        if not image_url or error != FetchError.NONE:
            error_msg = get_error_message(error)
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        view.seen.add(md5)
        await STATS_DB.record_action("succ", interaction.user.id, target.id, is_back=False)
        count = await STATS_DB.get_pair_count("succ", interaction.user.id, target.id)
        totals = await STATS_DB.get_user("succ", target.id)
        target_total = int(totals.get("received", 0))

        line = random.choice(SUCC_LINES_INTIMATE).format(actor=f"**{interaction.user.display_name}**", target=f"**{target.display_name}**")

        embed = build_action_embed(
            action_type="succ",
            actor=interaction.user,
            target=target,
            action_line=line,
            pair_count=count,
            target_total=target_total,
            source=site,
            is_back=False,
        )

        if file and fname:
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
