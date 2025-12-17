import discord
import logging

log = logging.getLogger("nyunzi")

# =========================
# SAFE INTERACTION ACK (prevents 10062)
# IMPORTANT: call this as the FIRST awaited line in every command/callback
# =========================
async def safe_defer(interaction: discord.Interaction, *, thinking: bool = True) -> bool:
    try:
        if not interaction.response.is_done():
            # Buttons / selects: NEVER use thinking=True (creates the stuck message in DMs)
            if interaction.type == discord.InteractionType.component:
                await interaction.response.defer(thinking=False)  # deferred message update
            else:
                await interaction.response.defer(thinking=thinking)
        return True
    except discord.NotFound:
        log.warning("[DEFER] Unknown interaction (10062) – clicked too late or network hiccup")
        return False
    except Exception as e:
        log.warning("[DEFER] failed: %s: %s", type(e).__name__, e)
        return False
