import random
import discord

def plap_summary(actor: discord.User, target: discord.User, count: int, target_total: int | None = None) -> str:
    """Second-line summary for /plap.

    - `count` is the directed pair count (actor -> target).
    - `target_total` (optional) is the total times the *target* has been plapped (all actors).
    """
    time_word = "time" if count == 1 else "times"
    
    actor_name = f"**{actor.display_name}**"
    target_name = f"**{target.display_name}**"

    # Sometimes show the target's total, if provided
    if target_total is not None and target_total >= 1 #and random.random() < 0.35:
        total_word = "time" if target_total == 1 else "times"
        total_pool = [
            f"{target_name} has been plapped a total of {target_total} {total_word}.",
            f"Total plaps on {target_name}: {target_total} {total_word}.",
            f"{target_name} has been plapped {target_total} {total_word} overall.",
        ]
        return random.choice(total_pool)

    if count <= 1:
        pool = [
            f"{actor_name} plapped {target_name} {count} {time_word}!",
            f"{actor_name} has plapped {target_name} {count} {time_word}.",
        ]
    elif count <= 3:
        pool = [
            f"{actor_name} has now plapped {target_name} {count} {time_word}!",
            f"{actor_name} keeps plapping {target_name} — {count} {time_word} now!",
            f"{count} {time_word} in, and {actor_name} isn’t stopping with {target_name}.",
        ]
    elif count <= 6:
        pool = [
            f"{actor_name} is not subtle — {count} {time_word} on {target_name}!",
            f"{count} {time_word} now… {actor_name} is making a point with {target_name}.",
            f"{actor_name} keeps coming back — {count} {time_word} and counting.",
        ]
    else:
        pool = [
            f"{count} {time_word}. Yeah. {actor_name} is absolutely locked in on {target_name}.",
            f"{actor_name} has lost count — but it’s at least {count} {time_word}.",
            f"{actor_name} keeps plapping {target_name}. Nobody’s pretending anymore ({count} {time_word}).",
        ]
    return random.choice(pool)


def succ_summary(actor: discord.User, target: discord.User, count: int) -> str:
    time_word = "time" if count == 1 else "times"
    
    actor_name = f"**{actor.display_name}**"
    target_name = f"**{target.display_name}**"
    
    if count <= 1:
        pool = [
            f"{actor_name} succ’d {target_name} {count} {time_word}!",
            f"{actor_name} has succ’d {target_name} {count} {time_word}.",
        ]
    elif count <= 3:
        pool = [
            f"{actor_name} has now succ’d {target_name} {count} {time_word}!",
            f"{actor_name} keeps succ’ing {target_name} — {count} {time_word} now!",
            f"{count} {time_word} in, and {actor_name} isn’t easing up on {target_name}.",
        ]
    elif count <= 6:
        pool = [
            f"{actor_name} is not subtle — {count} {time_word} on {target_name}!",
            f"{count} {time_word} now… {actor_name} is making a point with {target_name}.",
            f"{actor_name} keeps coming back — {count} {time_word} and counting.",
        ]
    else:
        pool = [
            f"{count} {time_word}. Yeah. {actor_name} is absolutely locked in on {target_name}.",
            f"{actor_name} has lost count — but it’s at least {count} {time_word}.",
            f"{actor_name} keeps succ’ing {target_name}. Nobody’s pretending anymore ({count} {time_word}).",
        ]
    return random.choice(pool)
