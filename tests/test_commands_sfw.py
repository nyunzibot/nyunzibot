
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fetch.pick import FetchError
import sys

for mod in ["commands.cuddle", "commands.kiss", "commands.pat", "commands.hug", "commands.poke"]:
    if mod in sys.modules:
        del sys.modules[mod]

@pytest.fixture
def mock_all_pickers():
    p1 = patch("commands.cuddle.pick_media_sfw", new_callable=AsyncMock)
    p2 = patch("commands.kiss.pick_media_sfw", new_callable=AsyncMock)
    p3 = patch("commands.pat.pick_media_sfw", new_callable=AsyncMock)
    p4 = patch("commands.hug.pick_media_sfw", new_callable=AsyncMock)
    p5 = patch("commands.poke.pick_media_sfw", new_callable=AsyncMock)
    
    yield (p1.start(), p2.start(), p3.start(), p4.start(), p5.start())
    p1.stop(); p2.stop(); p3.stop(); p4.stop(); p5.stop()

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
    return bot, captured

@pytest.mark.asyncio
async def test_sfw_commands_success(mock_interaction, mock_all_pickers, mock_bot_capture):
    bot, captured = mock_bot_capture
    (m_cuddle, m_kiss, m_pat, m_hug, m_poke) = mock_all_pickers
    
    valid_media = ("http://url.com/img.jpg", "md5", "safebooru", MagicMock(), "img.jpg", FetchError.NONE)
    for m in (m_cuddle, m_kiss, m_pat, m_hug, m_poke):
        m.return_value = valid_media
    
    from commands import cuddle, kiss, pat, hug, poke
    cuddle.setup(bot)
    kiss.setup(bot)
    pat.setup(bot)
    hug.setup(bot)
    poke.setup(bot)
    
    interaction, target = mock_interaction
    
    await captured["cuddle"](interaction, target, extra_tags=None)
    m_cuddle.assert_called()
    
    await captured["kiss"](interaction, target, extra_tags=None)
    m_kiss.assert_called()

@pytest.mark.asyncio
async def test_sfw_commands_self_target(mock_interaction, mock_bot_capture):
    bot, captured = mock_bot_capture
    from commands import cuddle
    cuddle.setup(bot)
    
    interaction, target = mock_interaction
    target.id = interaction.user.id
    
    await captured["cuddle"](interaction, target)
    assert interaction.followup.send.called or interaction.response.send_message.called
