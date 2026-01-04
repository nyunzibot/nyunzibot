import logging
import discord

from logging_setup import setup_logging
from config import TOKEN, RULE34_API_KEY, RULE34_USER_ID, GELBOORU_API_KEY, GELBOORU_USER_ID, DB_PATH
from bot.client import create_bot
from db.runtime import STATS_DB

from commands import plap as plap_cmd
from commands import succ as succ_cmd
from commands import stats as stats_cmd
from commands import bounce as bounce_cmd
from commands import cuddle as cuddle_cmd
from commands import kiss as kiss_cmd
from commands import pat as pat_cmd
from commands import hug as hug_cmd
from commands import poke as poke_cmd
from commands import tuck as tuck_cmd

def main():
    log = setup_logging()

    log.info("DB_PATH=%s", DB_PATH)
    log.info("Rule34 enabled=%s", bool(RULE34_API_KEY and RULE34_USER_ID))
    log.info("Gelbooru enabled=%s", bool(GELBOORU_API_KEY and GELBOORU_USER_ID))

    if not TOKEN:
        log.warning("TOKEN missing! Bot cannot log in (set Railway variable TOKEN).")
    if not (RULE34_API_KEY and RULE34_USER_ID):
        log.warning("RULE34_API_KEY or RULE34_USER_ID missing! Rule34 fetching will be skipped.")
    if not (GELBOORU_API_KEY and GELBOORU_USER_ID):
        log.warning("GELBOORU_API_KEY or GELBOORU_USER_ID missing! Gelbooru fetching will be skipped.")

    bot = create_bot()

    # Register commands
    plap_cmd.setup(bot)
    succ_cmd.setup(bot)
    stats_cmd.setup(bot)
    bounce_cmd.setup(bot)
    cuddle_cmd.setup(bot)
    kiss_cmd.setup(bot)
    pat_cmd.setup(bot)
    hug_cmd.setup(bot)
    poke_cmd.setup(bot)
    tuck_cmd.setup(bot)

    @bot.event
    async def on_ready():
        try:
            await bot.tree.sync()  # global sync for DMs
        except discord.errors.HTTPException as e:
            if e.status == 429:
                log.info("Rate limited during command sync (429). Skipping sync assuming commands are already registered.")
                if e.response is not None and hasattr(e.response, 'headers'):
                    headers = {
                        k: e.response.headers.get(k)
                        for k in ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-RateLimit-Reset-After", "X-RateLimit-Bucket"]
                    }
                    log.info("Rate Limit Headers: %s", headers)
            else:
                log.info("Failed to sync commands: %s", e)
        except Exception as e:
            log.info("Unexpected error during sync: %s", e)
        log.info("Logged in as %s", bot.user)
        log.info("Registered commands: %s", [c.name for c in bot.tree.get_commands()])

        log.info("Fetching Firebase users...")
        try:
            uids = await STATS_DB.get_all_user_ids()
            log.info("Found %d users in DB", len(uids))
            for uid in uids:
                try:
                    user = await bot.fetch_user(uid)
                    log.info("DB User: %s (@%s) [ID: %s]", user.display_name, user.name, uid)
                except discord.NotFound:
                    log.warning("DB User %s not found on Discord", uid)
                except discord.HTTPException as e:
                    log.warning("Failed to fetch user %s: %s", uid, e)
        except Exception as e:
            log.error("Failed to fetch/log DB users: %s", e)

    bot.run(TOKEN)

if __name__ == "__main__":
    main()
