"""
Rich Discord Embed Builder for Nyunzi Bot
Beautiful, visually appealing embeds with all Discord features
"""
import discord
from datetime import datetime, timezone
from typing import Optional
import random


# ═══════════════════════════════════════════════════════════════
# COLOR PALETTES - Beautiful gradient-inspired colors
# ═══════════════════════════════════════════════════════════════

class EmbedColors:
    """Premium color palette for different actions."""
    # Plap - Warm passionate tones
    PLAP_PRIMARY = 0xFF6B9D      # Hot pink
    PLAP_SECONDARY = 0xFF9E80    # Soft coral
    PLAP_GRADIENT = [0xFF6B9D, 0xFF8FA3, 0xFFB4AB]
    
    # Succ - Sweet candy vibes
    SUCC_PRIMARY = 0xE84393      # Deep magenta
    SUCC_SECONDARY = 0xFD79A8   # Soft pink
    SUCC_GRADIENT = [0xE84393, 0xFD79A8, 0xFAB1A0]
    
    # Bounce - Energetic purple
    BOUNCE_PRIMARY = 0xA855F7    # Vibrant purple
    BOUNCE_SECONDARY = 0xC084FC  # Light purple
    BOUNCE_GRADIENT = [0xA855F7, 0xC084FC, 0xE879F9]
    
    # Error states
    ERROR = 0xEF4444             # Red
    WARNING = 0xF59E0B           # Amber
    SUCCESS = 0x10B981           # Emerald


# ═══════════════════════════════════════════════════════════════
# DECORATIVE ELEMENTS
# ═══════════════════════════════════════════════════════════════

class Decorations:
    """Pretty decorative elements for embeds."""
    # Sparkles and stars
    SPARKLE = "✨"
    STAR = "⭐"
    STARS = "✧･ﾟ: *✧･ﾟ:*"
    MAGIC = "｡･:*:･ﾟ★"
    
    # Hearts
    HEART_PULSE = "💗"
    HEART_PINK = "💕"
    HEART_FIRE = "❤️‍🔥"
    HEART_ARROW = "💘"
    
    # Action emojis
    PLAP_EMOJI = "💢"
    SUCC_EMOJI = "🍬"
    BOUNCE_EMOJI = "🎀"
    
    # Dividers
    DIVIDER_FANCY = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    DIVIDER_DOTS = "• • • • • • • • •"
    DIVIDER_STARS = "✧ ✦ ✧ ✦ ✧ ✦ ✧"
    DIVIDER_WAVE = "〰️〰️〰️〰️〰️"
    
    # Stats icons
    STATS_ICON = "📊"
    COUNTER_ICON = "🔢"
    FIRE_ICON = "🔥"
    TARGET_ICON = "🎯"


# ═══════════════════════════════════════════════════════════════
# EMBED BUILDERS
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
) -> discord.Embed:
    """Build a beautiful, feature-rich embed for action commands."""
    
    # Select color and emoji based on action type
    colors = {
        "plap": EmbedColors.PLAP_PRIMARY,
        "succ": EmbedColors.SUCC_PRIMARY,
        "bounce": EmbedColors.BOUNCE_PRIMARY,
    }
    emojis = {
        "plap": "💢",
        "succ": "🍬", 
        "bounce": "🎀",
    }
    verbs = {
        "plap": ("plapped", "plaps"),
        "succ": ("succ'd", "succs"),
        "bounce": ("bounced on", "bounces on"),
    }
    
    color = colors.get(action_type, EmbedColors.PLAP_PRIMARY)
    emoji = emojis.get(action_type, "💫")
    past_verb, present_verb = verbs.get(action_type, ("used", "uses"))
    
    # Create embed with color
    embed = discord.Embed(color=discord.Color(color))
    
    # ─── Author Header ───
    action_word = f"{action_type}s back" if is_back else f"used /{action_type}"
    embed.set_author(
        name=f"{actor.display_name} {action_word}",
        icon_url=actor.display_avatar.url
    )
    
    # ─── Main Description ───
    description_parts = [
        f"{Decorations.SPARKLE} {action_line}",
        "",
        Decorations.DIVIDER_FANCY,
    ]
    embed.description = "\n".join(description_parts)
    
    # ─── Stats Fields ───
    # Pair stats
    time_word = "time" if pair_count == 1 else "times"
    
    # Streak indicator based on count
    if pair_count >= 10:
        streak = "🔥🔥🔥"
    elif pair_count >= 5:
        streak = "🔥🔥"
    elif pair_count >= 3:
        streak = "🔥"
    else:
        streak = ""
    
    embed.add_field(
        name=f"{emoji} Session Stats",
        value=f"```fix\n{actor.display_name} → {target.display_name}: {pair_count}x {streak}```",
        inline=True
    )
    
    # Target total if available
    if target_total is not None and target_total >= 1:
        embed.add_field(
            name=f"🎯 {target.display_name}'s Total",
            value=f"```yaml\nAll-time: {target_total}x```",
            inline=True
        )
    
    # ─── Footer ───
    footer_texts = [
        f"✨ Source: {source}",
        f"🌸 Source: {source}",
        f"💫 Source: {source}",
    ]
    embed.set_footer(
        text=random.choice(footer_texts),
    )
    
    # ─── Timestamp ───
    embed.timestamp = datetime.now(timezone.utc)
    
    return embed


def build_error_embed(
    error_message: str,
    *,
    title: str = "Oops!",
    suggestion: Optional[str] = None,
) -> discord.Embed:
    """Build a pretty error embed."""
    embed = discord.Embed(
        title=f"❌ {title}",
        description=error_message,
        color=discord.Color(EmbedColors.ERROR)
    )
    
    if suggestion:
        embed.add_field(
            name="💡 Suggestion",
            value=suggestion,
            inline=False
        )
    
    embed.set_footer(text="Try again in a moment!")
    return embed


# ═══════════════════════════════════════════════════════════════
# BUTTON STYLES - Enhanced button labels
# ═══════════════════════════════════════════════════════════════

class ButtonLabels:
    """Pretty button labels with emojis."""
    
    @staticmethod
    def refresh(remaining: int) -> str:
        if remaining <= 0:
            return "No refreshes left"
        return f"Refresh ({remaining})"
    
    @staticmethod
    def refresh_loading(dots: int = 1) -> str:
        return "Loading" + "." * dots
    
    @staticmethod
    def back_button(action: str) -> str:
        """Get the 'X back' button label."""
        labels = {
            "plap": "Plap back",
            "succ": "Succ back",
            "bounce": "Bounce back",
        }
        return labels.get(action, f"{action.title()} back")
    
    @staticmethod
    def again_button(action: str) -> str:
        """Get the 'X again' button label."""
        labels = {
            "plap": "Plap again",
            "succ": "Succ again",
            "bounce": "Bounce again",
        }
        return labels.get(action, f"{action.title()} again")
    
    @staticmethod
    def done_button(action: str) -> str:
        """Get the completed action button label."""
        labels = {
            "plap": "Plapped",
            "succ": "Succ'd",
            "bounce": "Bounced",
        }
        return labels.get(action, "Done")


# ═══════════════════════════════════════════════════════════════
# QUICK HELPERS
# ═══════════════════════════════════════════════════════════════

def get_action_color(action: str) -> discord.Color:
    """Get the color for an action type."""
    colors = {
        "plap": EmbedColors.PLAP_PRIMARY,
        "succ": EmbedColors.SUCC_PRIMARY,
        "bounce": EmbedColors.BOUNCE_PRIMARY,
    }
    return discord.Color(colors.get(action, EmbedColors.PLAP_PRIMARY))


def get_action_emoji(action: str) -> str:
    """Get the emoji for an action type."""
    emojis = {
        "plap": "💢",
        "succ": "🍬",
        "bounce": "🎀",
    }
    return emojis.get(action, "💫")
