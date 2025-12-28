
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.fixture(scope="function")
def mock_import_bot():
    import importlib.util
    import sys
    import os
    
    with patch("bot.client.create_bot") as m_create_bot:
        mock_bot = MagicMock()
        m_create_bot.return_value = mock_bot
        
        file_path = os.path.abspath("bot.py")
        module_name = "bot_entry_point"
        
        # MOCK DEPENDENCIES
        mock_log_module = MagicMock()
        mock_log_module.setup_logging = MagicMock()
        
        mock_config_module = MagicMock()
        mock_config_module.TOKEN = "fake_token"
        mock_config_module.RULE34_API_KEY = "k"
        mock_config_module.RULE34_USER_ID = "u"
        mock_config_module.GELBOORU_API_KEY = "k"
        mock_config_module.GELBOORU_USER_ID = "u"
        mock_config_module.DB_PATH = ":memory:"
        
        # Prepare modules
        sys.modules["logging_setup"] = mock_log_module
        sys.modules["config"] = mock_config_module
        
        # Clean reload
        if module_name in sys.modules:
            del sys.modules[module_name]

        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        
        # Patch command setups
        with patch("commands.plap.setup"), \
             patch("commands.succ.setup"), \
             patch("commands.stats.setup"), \
             patch("commands.bounce.setup"), \
             patch("commands.cuddle.setup"), \
             patch("commands.kiss.setup"), \
             patch("commands.pat.setup"), \
             patch("commands.hug.setup"), \
             patch("commands.poke.setup"):
             
            spec.loader.exec_module(module)
            yield module, mock_bot

def test_bot_startup(mock_import_bot):
    main_module, mock_bot = mock_import_bot 
    main_module.main()
    mock_bot.run.assert_called()

@pytest.mark.asyncio
async def test_bot_on_ready(mock_import_bot):
    main_module, mock_bot = mock_import_bot
    main_module.main()
    assert mock_bot.event.called
