
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.fixture
def mock_all_pickers_views():
    # Patch pick_image, NOT pick_media, because views import pick_image
    # OR: patch fetch.pick.pick_image if views import it directly?
    # views/plap_view.py: from fetch.pick import pick_image
    # Patch "views.plap_view.pick_image" is correct for that file import.
    # But we want a general fixture for other views too?
    # Let's patch where they are used.
    
    p1 = patch("views.plap_view.pick_image", new_callable=AsyncMock)
    p2 = patch("views.cuddle_view.pick_image_sfw", new_callable=AsyncMock)
    
    m1 = p1.start()
    m2 = p2.start()
    yield (m1, m2)
    p1.stop()
    p2.stop()

@pytest.mark.asyncio
async def test_view_permissions(mock_interaction):
    from views.plap_view import PlapBackView
    
    interaction, target = mock_interaction
    view = PlapBackView(interaction.user, target)
    button = MagicMock()

    # 1. Reroll by wrong user
    wrong_user_interaction = AsyncMock()
    wrong_user_interaction.user.id = 99999
    
    with patch("views.plap_view.safe_defer", new_callable=AsyncMock) as m_defer:
        m_defer.return_value = True 
        
        await view.reroll(wrong_user_interaction, button)
        
        wrong_user_interaction.followup.send.assert_called_with("Only the sender can refresh 🔄", ephemeral=True)

@pytest.mark.asyncio
async def test_view_timeout(mock_interaction):
    from views.plap_view import PlapBackView
    interaction, target = mock_interaction
    view = PlapBackView(interaction.user, target)
    view.message = AsyncMock()

    btn = MagicMock()
    view.children = [btn]
    
    await view.on_timeout()
    
    assert btn.disabled is True
    view.message.edit.assert_called()

@pytest.mark.asyncio
async def test_view_interactions(mock_interaction, mock_all_pickers_views):
    from views.plap_view import PlapBackView
    mock_pick_nsfw, mock_pick_sfw = mock_all_pickers_views

    from fetch.pick import FetchError
    # pick_image returns (url, md5, site) directly? No, it returns (picked_tuple, error).
    # picked_tuple is (url, md5, site).
    mock_pick_nsfw.return_value = (("http://url.com/img.jpg", "md5", "site"), FetchError.NONE)

    interaction, target = mock_interaction
    interaction.user.id = 12345
    
    view = PlapBackView(interaction.user, target)
    button = MagicMock()

    # 1. Reroll (Success)
    with patch("views.plap_view.process_image", new_callable=AsyncMock) as m_proc, \
         patch("views.plap_view.safe_defer", new_callable=AsyncMock) as m_defer:
        
        m_defer.return_value = True
        m_proc.return_value = (MagicMock(), "img.jpg", None)
        
        await view.reroll(interaction, button)
        m_proc.assert_called()

@pytest.mark.asyncio
async def test_kiss_view_reroll_multi(mock_interaction):
    from views.kiss_view import KissView
    interaction, target = mock_interaction
    interaction.user.id = 12345
    
    view = KissView(interaction.user, target)
    view.message = AsyncMock() # Mock message for edit
    button = MagicMock()
    
    # Mock dependencies
    with patch("views.kiss_view.pick_media_sfw", new_callable=AsyncMock) as m_pick, \
         patch("views.kiss_view.safe_defer", new_callable=AsyncMock) as m_defer, \
         patch("views.kiss_view.STATS_DB", new_callable=AsyncMock) as m_db:
         
        m_defer.return_value = True
        
        # Mock DB
        m_db.get_pair_count.return_value = 10
        m_db.get_user.return_value = {"received": 5}
        
        # Test Multi-Image Case
        from fetch.pick_safebooru import FetchError
        # Return: (image_url_or_urls, md5, site, file_or_files, fname_or_fnames, error)
        # Multi-image:
        m_pick.return_value = (
            ["http://url1.jpg", "http://url2.jpg"], 
            "md5_hash", 
            "safebooru", 
            [MagicMock(), MagicMock()], # Files
            ["img1.jpg", "img2.jpg"],   # Fnames
            FetchError.NONE
        )
        
        await view.reroll(interaction, button)
        
        # Verify pick called
        m_pick.assert_called_once()
        
        # Verify edit called with embeds list
        interaction.followup.edit_message.assert_called()
        call_args = interaction.followup.edit_message.call_args
        assert "embeds" in call_args.kwargs
        assert len(call_args.kwargs["embeds"]) > 1
        assert "attachments" in call_args.kwargs
        assert len(call_args.kwargs["attachments"]) == 2
