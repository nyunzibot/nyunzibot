import logging
from config import DB_PATH
from db.firestore_stats import FirestoreStatsDB

log = logging.getLogger("nyunzi")

STATS_DB = FirestoreStatsDB()
log.info("DB_PATH=%s", DB_PATH)
