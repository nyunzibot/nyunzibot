"""
Rich Discord Embed Styling for Nyunzi Bot
Clean, beautiful embeds with subtle accents
"""
import discord
from typing import Optional
import random


# ═══════════════════════════════════════════════════════════════
# COLOR PALETTES - Beautiful, vibrant colors
# ═══════════════════════════════════════════════════════════════

class EmbedColors:
    """Premium color palette for different actions."""
    # Plap - Warm passionate tones
    PLAP = 0xFF6B9D       # Hot pink
    
    # Succ - Sweet candy vibes  
    SUCC = 0xE84393       # Deep magenta
    
    # Bounce - Energetic purple
    BOUNCE = 0xA855F7     # Vibrant purple
    
    # Error states
    ERROR = 0xEF4444      # Red


# ═══════════════════════════════════════════════════════════════
# DECORATIVE ACCENTS - Subtle and pretty
# ═══════════════════════════════════════════════════════════════

class Accents:
    """Subtle decorative accents."""
    SPARKLE = "✨"
    STAR = "⭐"
    HEART = "💕"
    
    # Action emojis for author line
    PLAP_EMOJI = "💢"
    SUCC_EMOJI = "🍬"
    BOUNCE_EMOJI = "🎀"
    
    @staticmethod
    def random_sparkle() -> str:
        """Get a random sparkle prefix."""
        options = ["✨", "⭐", "💫", "✧"]
        return random.choice(options)


# ═══════════════════════════════════════════════════════════════
# EMBED BUILDER - Clean and elegant
# ═══════════════════════════════════════════════════════════════

def build_action_embed(
    *,
    action_type: str,  # "plap", "succ", "bounce"
    actor: discord.User,
    target: discord.User,
    action_line: str,
    pair_count: int,
    target_total: Optional[int] = None,
    source: str,
    is_back: bool = False,
    disable_prefix: bool = False,
) -> discord.Embed:
    """Build a clean, beautiful embed for action commands."""
    
    # Select color based on action type
    colors = {
        "plap": EmbedColors.PLAP,
        "succ": EmbedColors.SUCC,
        "bounce": EmbedColors.BOUNCE,
    }
    
    color = colors.get(action_type, EmbedColors.PLAP)
    
    # Build summary line
    past_tense_map = {
        "plap": "plapped",
        "succ": "succed",
        "bounce": "bounced",
        "kiss": "kissed",
        "hug": "hugged",
        "pat": "patted",
        "poke": "poked",
        "cuddle": "cuddled",
        "tuck": "tucked",
    }
    past_action = past_tense_map.get(action_type, f"{action_type}ped")
    
    time_word = "time" if target_total == 1 else "times"
    if target_total is not None and target_total >= 1:
        summary = f"**{target.display_name}** has been {past_action} a total of {target_total} {time_word}."
    else:
        summary = ""
    
    # Build description with sparkle accent
    if disable_prefix:
        term_line = action_line
    else:
        sparkle = Accents.random_sparkle()
        term_line = f"{sparkle} {action_line}" if action_line else ""
    
    if summary:
        sep = "\n\n" if term_line else ""
        description = f"{term_line}{sep}{summary}\n\n`source: {source}`"
    else:
        description = f"{term_line}\n\n`source: {source}`" if term_line else f"`source: {source}`"
    
    # Create embed
    embed = discord.Embed(
        description=description,
        color=discord.Color(color),
    )
    
    # Author header
    action_word = f"{action_type}s back" if is_back else f"used /{action_type}"
    embed.set_author(
        name=f"{actor.display_name} {action_word}",
        icon_url=actor.display_avatar.url
    )
    
    return embed


def build_error_embed(
    error_message: str,
    *,
    title: str = "Oops!",
) -> discord.Embed:
    """Build a pretty error embed."""
    embed = discord.Embed(
        description=f"❌ {error_message}",
        color=discord.Color(EmbedColors.ERROR)
    )
    return embed


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def get_action_color(action: str) -> discord.Color:
    """Get the color for an action type."""
    colors = {
        "plap": EmbedColors.PLAP,
        "succ": EmbedColors.SUCC,
        "bounce": EmbedColors.BOUNCE,
    }
    return discord.Color(colors.get(action, EmbedColors.PLAP))


def get_action_emoji(action: str) -> str:
    """Get the emoji for an action type."""
    emojis = {
        "plap": "💢",
        "succ": "🍬",
        "bounce": "🎀",
    }
    return emojis.get(action, "💫")


def build_multi_image_embeds(
    main_embed: discord.Embed,
    filenames: list[str],
) -> list[discord.Embed]:
    """
    Build a list of embeds for multi-image gallery display.
    
    Discord displays multiple embeds as a gallery when they share the same `url`.
    The first embed contains the main content, subsequent embeds just have images.
    
    Args:
        main_embed: The primary embed with content
        filenames: List of attachment filenames
        
    Returns:
        List of embeds to send together
    """
    if not filenames:
        return [main_embed]
    
    # Use a consistent URL to link embeds together for gallery display
    gallery_url = "https://gelbooru.com"
    
    # Set the URL on main embed and first image
    main_embed.url = gallery_url
    main_embed.set_image(url=f"attachment://{filenames[0]}")
    
    embeds = [main_embed]
    
    # Create additional embeds for remaining images (same URL = gallery)
    for fname in filenames[1:]:
        img_embed = discord.Embed(url=gallery_url)
        img_embed.set_image(url=f"attachment://{fname}")
        embeds.append(img_embed)
    
    return embeds

