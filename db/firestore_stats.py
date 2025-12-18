import os
import json
import time
import asyncio
import firebase_admin
from firebase_admin import credentials, firestore


class FirestoreStatsDB:
    def __init__(self):
        self.db = self._init_firestore()

    def _init_firestore(self):
        raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

        if not raw:
            firebase_keys = [k for k in os.environ.keys() if k.startswith("FIREBASE_")]
            raise RuntimeError(
                "Missing env var FIREBASE_SERVICE_ACCOUNT_JSON in this running service/environment. "
                f"FIREBASE_* vars present: {firebase_keys}"
            )

        cred = credentials.Certificate(json.loads(raw))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        return firestore.client()

    async def _run(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    @staticmethod
    def _user_doc_id(user_id: int) -> str:
        return str(user_id)

    @staticmethod
    def _field(action: str, kind: str) -> str:
        # action: "plap" / "succ"
        # kind: "given" / "received"
        return f"{action}_{kind}"

    async def record_action(self, action: str, actor_id: int, target_id: int, is_back: bool):
        """
        Records:
          actor  -> <action>_given += 1
          target -> <action>_received += 1
        """
        def work():
            inc = firestore.Increment(1)

            actor_ref = self.db.collection("users").document(self._user_doc_id(actor_id))
            target_ref = self.db.collection("users").document(self._user_doc_id(target_id))

            actor_updates = {
                "user_id": str(actor_id),
                self._field(action, "given"): inc,
            }

            target_updates = {
                "user_id": str(target_id),
                self._field(action, "received"): inc,
            }

            batch = self.db.batch()
            batch.set(actor_ref, actor_updates, merge=True)
            batch.set(target_ref, target_updates, merge=True)
            batch.commit()

        await self._run(work)

    async def get_user(self, action: str, user_id: int) -> dict:
        """
        Returns:
          {"given": x, "received": y}
        """
        def work():
            ref = self.db.collection("users").document(self._user_doc_id(user_id))
            snap = ref.get()

            if not snap.exists:
                ref.set({"user_id": str(user_id)}, merge=True)
                return {"given": 0, "received": 0}

            d = snap.to_dict() or {}
            return {
                "given": int(d.get(self._field(action, "given"), 0)),
                "received": int(d.get(self._field(action, "received"), 0)),
            }

        return await self._run(work)

    async def mark_seen(self, md5: str, site: str):
        def work():
            ref = self.db.collection("seen_md5").document(md5)
            ref.create(
                {
                    "md5": md5,
                    "site": site,
                    "first_seen": int(time.time()),
                }
            )

        try:
            await self._run(work)
        except Exception:
            # already exists → ignore
            return

    async def load_recent_seen(self, max_age_days: int = 30) -> set[str]:
        cutoff = int(time.time()) - max_age_days * 86400

        def work():
            qs = self.db.collection("seen_md5").where("first_seen", ">=", cutoff)
            out = set()
            for doc in qs.stream():
                d = doc.to_dict() or {}
                md5 = d.get("md5") or doc.id
                if md5:
                    out.add(md5)
            return out

        return await self._run(work)
