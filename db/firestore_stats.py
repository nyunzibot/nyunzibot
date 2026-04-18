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
        # 1. Try explicit service account JSON (local dev or non-Google env)
        # Fallback to checking with \n because of a Railway dashboard copy/paste bug
        raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON\n")
        if raw:
            cred = credentials.Certificate(json.loads(raw))
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            return firestore.client()
        
        # 2. Try Application Default Credentials (ADC) - for Cloud Run / GCE
        # This works if the environment is set up (e.g. gcloud auth application-default login)
        # or running on Google Cloud infrastructure.
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app()  # No args = use ADC
            return firestore.client()
        except Exception as e:
            firebase_keys = [k for k in os.environ.keys() if k.startswith("FIREBASE_")]
            raise RuntimeError(
                f"Failed to initialize Firestore. Env var FIREBASE_SERVICE_ACCOUNT_JSON missing, "
                f"and ADC failed ({e}). FIREBASE_* vars present: {firebase_keys}"
            )

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

    @staticmethod
    def _pair_doc_id(actor_id: int, target_id: int) -> str:
        # Directed pair: actor -> target
        return f"{actor_id}_{target_id}"

    @staticmethod
    def _pair_field(action: str) -> str:
        return f"{action}_count"

    # -------------------------
    # Per-pair persistent seen
    # -------------------------
    @staticmethod
    def _seen_pair_doc_id(user_a: int, user_b: int) -> str:
        # Unordered pair: (A,B) is same as (B,A)
        lo, hi = (user_a, user_b) if user_a < user_b else (user_b, user_a)
        return f"{lo}_{hi}"

    async def load_pair_seen(self, user_a: int, user_b: int) -> list[str]:
        """Return rolling md5 list (oldest -> newest) for this unordered pair."""
        def work():
            ref = self.db.collection("pair_seen").document(self._seen_pair_doc_id(user_a, user_b))
            snap = ref.get()
            if not snap.exists:
                return []
            d = snap.to_dict() or {}
            md5s = d.get("md5s") or []
            return list(md5s)

        try:
            return await self._run(work)
        except Exception:
            return []

    async def add_pair_seen(self, user_a: int, user_b: int, md5: str, site: str | None = None, max_entries: int = 1000):
        """Atomically add md5 to the pair's rolling list (max_entries, drop oldest)."""
        def work():
            docref = self.db.collection("pair_seen").document(self._seen_pair_doc_id(user_a, user_b))

            @firestore.transactional
            def txn_update(txn: firestore.Transaction):
                snap = docref.get(transaction=txn)
                if snap.exists:
                    d = snap.to_dict() or {}
                    md5s = list(d.get("md5s") or [])
                else:
                    md5s = []

                # Move-to-end if already present (keeps "recent" ordering clean)
                if md5 in md5s:
                    try:
                        md5s.remove(md5)
                    except ValueError:
                        pass
                md5s.append(md5)

                # Trim oldest beyond max_entries
                if len(md5s) > max_entries:
                    md5s = md5s[-max_entries:]

                data = {"md5s": md5s, "updated_at": firestore.SERVER_TIMESTAMP}
                if site:
                    data["last_site"] = site
                txn.set(docref, data, merge=True)

            txn = self.db.transaction()
            txn_update(txn)

        try:
            await self._run(work)
        except Exception:
            pass

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
            pair_ref = self.db.collection("pairs").document(self._pair_doc_id(actor_id, target_id))

            actor_updates = {
                "user_id": str(actor_id),
                self._field(action, "given"): inc,
            }

            target_updates = {
                "user_id": str(target_id),
                self._field(action, "received"): inc,
            }

            pair_updates = {
                "actor_id": str(actor_id),
                "target_id": str(target_id),
                self._pair_field(action): inc,
            }

            batch = self.db.batch()
            batch.set(actor_ref, actor_updates, merge=True)
            batch.set(target_ref, target_updates, merge=True)
            batch.set(pair_ref, pair_updates, merge=True)
            batch.commit()

        try:
            await self._run(work)
        except Exception as e:
            # Log specific warning for feedback but don't crash
            import logging
            log = logging.getLogger("nyunzi")
            log.warning("DB Error during record_action (stats not saved): %s", e)

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

        try:
            return await self._run(work)
        except Exception:
            return {"given": 0, "received": 0}

    async def get_pair_count(self, action: str, actor_id: int, target_id: int) -> int:
        """Return directed pair count for actor -> target for the given action."""
        def work():
            ref = self.db.collection("pairs").document(self._pair_doc_id(actor_id, target_id))
            snap = ref.get()
            if not snap.exists:
                ref.set({
                    "actor_id": str(actor_id),
                    "target_id": str(target_id),
                    self._pair_field(action): 0,
                }, merge=True)
                return 0
            d = snap.to_dict() or {}
            return int(d.get(self._pair_field(action), 0))

        try:
            return await self._run(work)
        except Exception:
            return 0

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
            # already exists or DB failure → ignore
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

        try:
            return await self._run(work)
        except Exception:
            return set()

    async def get_all_user_ids(self) -> list[int]:
        """Fetch all user IDs from the users collection."""
        def work():
            docs = self.db.collection("users").stream()
            user_ids = []
            for doc in docs:
                d = doc.to_dict() or {}
                # The user_id field is stored as string in record_action/get_user
                uid = d.get("user_id")
                if uid:
                    try:
                        user_ids.append(int(uid))
                    except ValueError:
                        pass
            return user_ids

        try:
            return await self._run(work)
        except Exception:
            return []
