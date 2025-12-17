import logging
from config import DB_PATH
from .stats import StatsDB

log = logging.getLogger("nyunzi")

STATS_DB = StatsDB(DB_PATH)
log.info("DB_PATH=%s", DB_PATH)
