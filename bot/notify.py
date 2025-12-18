import random
import discord
import logging

from text.notify_lines import PLAP_NOTIFY_LINES, SUCC_NOTIFY_LINES

log = logging.getLogger("nyunzi")

async def send_dm_notify(kind: str, actor: discord.abc.User, target: discord.abc.User) -> None:
    """Send a DM notification to target. Best-effort; silently fails on permission errors."""
    try:
        actor_name = getattr(actor, "display_name", None) or str(actor)
        if kind == "plap":
            title = f"💥 **{actor_name} just plapped you!**"
            second = random.choice(PLAP_NOTIFY_LINES).format(actor=actor_name)
        else:
            title = f"💞 **{actor_name} just succ’d you!**"
            second = random.choice(SUCC_NOTIFY_LINES).format(actor=actor_name)

        # Keep content short for mobile notifications
        await target.send(f"{title}\n{second}")
    except Exception as e:
        # Don't spam logs at high volume; keep as debug/info.
        try:
            log.info("[DM NOTIFY] kind=%s actor=%s target=%s failed=%s", kind, getattr(actor, "id", "?"), getattr(target, "id", "?"), type(e).__name__)
        except Exception:
            pass
