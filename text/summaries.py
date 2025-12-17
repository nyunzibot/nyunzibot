import random
import discord

def plap_summary(actor: discord.User, target: discord.User, count: int) -> str:
    time_word = "time" if count == 1 else "times"
    if count <= 1:
        pool = [
            f"{actor.mention} plapped {target.mention} {count} {time_word}!",
            f"{actor.mention} has plapped {target.mention} {count} {time_word}.",
        ]
    elif count <= 3:
        pool = [
            f"{actor.mention} has now plapped {target.mention} {count} {time_word}!",
            f"{actor.mention} keeps plapping {target.mention} — {count} {time_word} now!",
            f"{count} {time_word} in, and {actor.mention} isn’t stopping with {target.mention}.",
        ]
    elif count <= 6:
        pool = [
            f"{actor.mention} is on a roll — {count} {time_word} on {target.mention}!",
            f"{count} {time_word} now… {actor.mention} is clearly committed to {target.mention}.",
            f"{actor.mention} keeps coming back — {count} {time_word} and counting.",
        ]
    else:
        pool = [
            f"{count} {time_word}. Yeah. {actor.mention} is absolutely not done with {target.mention}.",
            f"{actor.mention} has lost count — but it’s at least {count} {time_word}.",
            f"{actor.mention} keeps plapping {target.mention}. Nobody’s pretending anymore ({count} {time_word}).",
        ]
    return random.choice(pool)

def succ_summary(actor: discord.User, target: discord.User, count: int) -> str:
    time_word = "time" if count == 1 else "times"
    if count <= 1:
        pool = [
            f"{actor.mention} succ’d {target.mention} {count} {time_word}!",
            f"{actor.mention} has succ’d {target.mention} {count} {time_word}.",
        ]
    elif count <= 3:
        pool = [
            f"{actor.mention} has now succ’d {target.mention} {count} {time_word}!",
            f"{actor.mention} keeps succ’ing {target.mention} — {count} {time_word} now!",
            f"{count} {time_word} in, and {actor.mention} isn’t easing up on {target.mention}.",
        ]
    elif count <= 6:
        pool = [
            f"{actor.mention} is not subtle — {count} {time_word} on {target.mention}!",
            f"{count} {time_word} now… {actor.mention} is making a point with {target.mention}.",
            f"{actor.mention} keeps coming back — {count} {time_word} and counting.",
        ]
    else:
        pool = [
            f"{count} {time_word}. Yeah. {actor.mention} is absolutely locked in on {target.mention}.",
            f"{actor.mention} has lost count — but it’s at least {count} {time_word}.",
            f"{actor.mention} keeps succ’ing {target.mention}. Nobody’s pretending anymore ({count} {time_word}).",
        ]
    return random.choice(pool)
