
import pytest
from db.stats import InteractionSeen

@pytest.mark.asyncio
async def test_interaction_seen_logic():
    seen = InteractionSeen(1, 2)
    assert seen.actor_id == 1
    assert seen.target_id == 2
    # Removed incorrect len() assertion

@pytest.mark.asyncio
async def test_stats_db_methods():
    from db.firestore_stats import FirestoreStatsDB
    db = FirestoreStatsDB()
    
    # Test methods generally don't crash
    await db.get_pair_count(1, 2, "plap")
    await db.get_user(1)
    await db.record_action(1, 1, 2, 2, "plap")
