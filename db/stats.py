import os
import time
import sqlite3
import asyncio

class StatsDB:
    def __init__(self, path: str):
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        dirn = os.path.dirname(self.path)
        if dirn:
            os.makedirs(dirn, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    action TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    given INTEGER NOT NULL DEFAULT 0,
                    received INTEGER NOT NULL DEFAULT 0,
                    backs INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (action, user_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_md5 (
                    md5 TEXT PRIMARY KEY,
                    site TEXT NOT NULL,
                    first_seen INTEGER NOT NULL
                )
            """)
            conn.commit()

    async def _run(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    async def record_action(self, action: str, actor_id: int, target_id: int, is_back: bool):
        def work():
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO stats(action, user_id, given, received, backs) VALUES(?, ?, 0, 0, 0)",
                    (action, str(actor_id)),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO stats(action, user_id, given, received, backs) VALUES(?, ?, 0, 0, 0)",
                    (action, str(target_id)),
                )

                if is_back:
                    conn.execute(
                        "UPDATE stats SET given = given + 1, backs = backs + 1 WHERE action = ? AND user_id = ?",
                        (action, str(actor_id)),
                    )
                else:
                    conn.execute(
                        "UPDATE stats SET given = given + 1 WHERE action = ? AND user_id = ?",
                        (action, str(actor_id)),
                    )

                conn.execute(
                    "UPDATE stats SET received = received + 1 WHERE action = ? AND user_id = ?",
                    (action, str(target_id)),
                )
                conn.commit()

        await self._run(work)

    async def get_user(self, action: str, user_id: int) -> dict:
        def work():
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO stats(action, user_id, given, received, backs) VALUES(?, ?, 0, 0, 0)",
                    (action, str(user_id)),
                )
                row = conn.execute(
                    "SELECT given, received, backs FROM stats WHERE action = ? AND user_id = ?",
                    (action, str(user_id)),
                ).fetchone()
                conn.commit()
                return {"given": row[0], "received": row[1], "backs": row[2]}

        return await self._run(work)

    async def mark_seen(self, md5: str, site: str):
        def work():
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO seen_md5(md5, site, first_seen) VALUES (?, ?, ?)",
                    (md5, site, int(time.time())),
                )
                conn.commit()

        await self._run(work)

    async def load_recent_seen(self, max_age_days: int = 30) -> set[str]:
        cutoff = int(time.time()) - max_age_days * 86400

        def work():
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT md5 FROM seen_md5 WHERE first_seen >= ?",
                    (cutoff,),
                ).fetchall()
                return {r[0] for r in rows if r and r[0]}

        return await self._run(work)

# =========================
# PER-INTERACTION DEDUP
# =========================
class InteractionSeen:
    def __init__(self, actor_id: int | None = None, target_id: int | None = None):
        # Per-interaction/session dedup (in-memory)
        self.md5s: set[str] = set()
        # Optional context so pickers can do persistent per-pair dedup
        self.actor_id: int | None = actor_id
        self.target_id: int | None = target_id

    def add(self, md5: str | None):
        if md5:
            self.md5s.add(md5)

    def has(self, md5: str | None) -> bool:
        return bool(md5) and md5 in self.md5s
