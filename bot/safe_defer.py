import discord
import logging

log = logging.getLogger("nyunzi")

# =========================
# SAFE INTERACTION ACK (prevents 10062)
# IMPORTANT: call this as the FIRST awaited line in every command/callback
# =========================
async def safe_defer(
    interaction: discord.Interaction,
    *,
    thinking: bool = True,
    components_thinking: bool | None = None,  # ✅ NEW
) -> bool:
    try:
        if not interaction.response.is_done():
            # Buttons / selects: default to thinking=False (DM-safe),
            # but allow opting-in to thinking=True for spinners.
            if interaction.type == discord.InteractionType.component:
                use_thinking = thinking if components_thinking is None else components_thinking
                await interaction.response.defer(thinking=use_thinking)
            else:
                await interaction.response.defer(thinking=thinking)
        return True
    except discord.NotFound:
        log.warning("[DEFER] Unknown interaction (10062) – clicked too late or network hiccup")
        return False
    except Exception as e:
        log.warning("[DEFER] failed: %s: %s", type(e).__name__, e)
        return False
