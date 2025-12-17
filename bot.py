import logging

from logging_setup import setup_logging
from config import TOKEN, RULE34_API_KEY, RULE34_USER_ID, GELBOORU_API_KEY, GELBOORU_USER_ID, DB_PATH
from bot.client import create_bot

from commands import plap as plap_cmd
from commands import succ as succ_cmd
from commands import stats as stats_cmd

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

    @bot.event
    async def on_ready():
        await bot.tree.sync()  # global sync for DMs
        log.info("Logged in as %s", bot.user)
        log.info("Registered commands: %s", [c.name for c in bot.tree.get_commands()])

    bot.run(TOKEN)

if __name__ == "__main__":
    main()
