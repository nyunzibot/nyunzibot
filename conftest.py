import sys
import os
from unittest.mock import MagicMock

print("DEBUG: Loading conftest.py and applying mocks...")

# 1. Mock firebase dependencies
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()

# 2. Mock db.firestore_stats entirely to bypass imports
mock_firestore_stats = MagicMock()
sys.modules["db.firestore_stats"] = mock_firestore_stats

# 3. Create a mock FirestoreStatsDB class so usage like FirestoreStatsDB() works
class MockFirestoreStatsDB:
    def __init__(self, *args, **kwargs):
        pass
    def __getattr__(self, name):
        return MagicMock()
    
# Assign this mock class to the module mock
mock_firestore_stats.FirestoreStatsDB = MockFirestoreStatsDB

# 4. Set env var just in case
os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"] = "{}"

import pytest

@pytest.fixture(autouse=True)
def mock_logging():
    with os.popen("python -c 'pass'") as _: 
        pass
    import logging
    logging.getLogger("nyunzi").setLevel(logging.CRITICAL)
