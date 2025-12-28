
import sys
import os
import asyncio
import io
import discord 
from unittest.mock import MagicMock, AsyncMock, patch

# --- MOCK FIREBASE ---
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()

mock_firestore_stats = MagicMock()
sys.modules["db.firestore_stats"] = mock_firestore_stats

class MockFirestoreStatsDB:
    def __init__(self, *args, **kwargs): pass
    def __getattr__(self, name): return AsyncMock()
    async def get_pair_count(self, *args, **kwargs): return 5
    async def get_user(self, *args, **kwargs): return {"received": 10, "given": 10}
    async def record_action(self, *args, **kwargs): return None
    async def add_pair_seen(self, *args, **kwargs): return None
    async def load_pair_seen(self, *args, **kwargs): return []

mock_firestore_stats.FirestoreStatsDB = MockFirestoreStatsDB

os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"] = "{}"

# --- MOCK DISCORD ---
mock_discord = MagicMock()
sys.modules["discord"] = mock_discord

# Mock classes that are inherited
class MockView:
    def __init__(self, *args, **kwargs): 
        self._children = []
    
    def add_item(self, item): 
        self._children.append(item)
        
    async def wait(self): return True
    def stop(self): pass
    async def on_timeout(self): pass
    
    @property
    def children(self): return self._children
    
    @children.setter
    def children(self, value): self._children = value

mock_discord.ui.View = MockView
mock_discord.ui.Button = MagicMock
mock_discord.File = MagicMock

# decorators
def identity(func):
    return func

def flexible_decorator(*args, **kwargs):
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]
    return identity

mock_discord.ui.button = flexible_decorator

# app_commands
mock_app_commands = MagicMock()
for method in ["command", "describe", "choices", "autocomplete", "allowed_contexts", "allowed_installs", "check", "guild_only", "default_permissions"]:
    getattr(mock_app_commands, method).side_effect = flexible_decorator

mock_app_commands.checks.cooldown.side_effect = flexible_decorator
mock_app_commands.checks.has_permissions.side_effect = flexible_decorator

sys.modules["discord.ui"] = mock_discord.ui
sys.modules["discord.app_commands"] = mock_app_commands
sys.modules["discord.ext"] = MagicMock()

# LINK mock_discord.app_commands TO mock_app_commands!
mock_discord.app_commands = mock_app_commands

import pytest

@pytest.fixture(autouse=True)
def mock_logging():
    import logging
    logging.getLogger("nyunzi").setLevel(logging.CRITICAL)

@pytest.fixture(autouse=True)
def mock_sleep():
    with patch("asyncio.sleep", new_callable=AsyncMock):
        yield

@pytest.fixture
def mock_interaction():
    interaction = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.user.display_name = "TestActor"
    interaction.user.mention = "<@12345>"
    
    interaction.response = AsyncMock()
    interaction.response.is_done.return_value = False # DEFAULT TO FALSE
    
    interaction.followup = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    
    target = MagicMock()
    target.id = 67890
    target.display_name = "TestTarget"
    target.mention = "<@67890>"
    
    return interaction, target
