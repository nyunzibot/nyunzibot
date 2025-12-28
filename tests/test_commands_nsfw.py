
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fetch.pick import FetchError
import sys

# clean sys.modules of command modules to ensure they reload with our mocks if needed
for mod in ["commands.plap", "commands.succ", "commands.bounce", "commands.cuddle", "commands.kiss", "commands.pat", "commands.hug", "commands.poke"]:
    if mod in sys.modules:
        del sys.modules[mod]

@pytest.fixture
def mock_all_pickers_nsfw():
    p1 = patch("commands.plap.pick_media", new_callable=AsyncMock)
    p2 = patch("commands.succ.pick_media", new_callable=AsyncMock)
    p3 = patch("commands.bounce.pick_media", new_callable=AsyncMock)
    
    m1 = p1.start()
    m2 = p2.start()
    m3 = p3.start()
    yield (m1, m2, m3)
    p1.stop()
    p2.stop()
    p3.stop()

@pytest.fixture
def mock_bot_capture():
    captured = {}
    def command_decorator(*args, **kwargs):
        def decorator(func):
            name = kwargs.get("name") or func.__name__
            captured[name] = func
            return func
        return decorator

    bot = MagicMock()
    bot.tree.command.side_effect = command_decorator
    
    # Also patch defaults to be safe for any missed decorators
    # handled by conftest? yes.
    
    return bot, captured

@pytest.mark.asyncio
async def test_nsfw_commands_success(mock_interaction, mock_all_pickers_nsfw, mock_bot_capture):
    bot, captured = mock_bot_capture
    (m_plap, m_succ, m_bounce) = mock_all_pickers_nsfw
    
    valid_media = ("http://url.com/img.jpg", "md5", "gelbooru", MagicMock(), "img.jpg", FetchError.NONE)
    m_plap.return_value = valid_media
    m_succ.return_value = valid_media
    m_bounce.return_value = valid_media
    
    # Forces fresh import logic if we deleted modules
    from commands import plap, succ, bounce 
    plap.setup(bot)
    succ.setup(bot)
    bounce.setup(bot)
    
    interaction, target = mock_interaction
    
    await captured["plap"](interaction, target, extra_tags=None)
    m_plap.assert_called()
    assert interaction.edit_original_response.called
    
    await captured["succ"](interaction, target, extra_tags=None)
    m_succ.assert_called()
    
    await captured["bounce"](interaction, target, extra_tags=None)
    m_bounce.assert_called()

@pytest.mark.asyncio
async def test_plap_self_target(mock_interaction, mock_bot_capture):
    bot, captured = mock_bot_capture
    from commands import plap
    plap.setup(bot)
    
    interaction, target = mock_interaction
    target.id = interaction.user.id
    
    await captured["plap"](interaction, target)
    
    # Check for failure message. Plap defers, so it uses followup or edit_original_response?
    # plap calls safe_defer. 
    # if successful: followup.send or edit_original_response
    # code says: await interaction.followup.send("Not yourself 😅", ephemeral=True)
    
    assert interaction.followup.send.called or interaction.response.send_message.called
