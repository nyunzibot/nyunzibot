
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fetch.pick_safebooru import pick_media_sfw, FetchError
from images.process import ProcessError

@pytest.fixture
def seen_set():
    return set()

@pytest.fixture
def mock_fetch_image():
    # pick_media_sfw calls `pick_image_sfw` which calls `fetch_image` (generic)
    # Actually, let's verify if I should mock `pick_image_sfw` or `fetch_image`.
    # `pick_media_sfw` calls `pick_image_sfw`.
    # `pick_image_sfw` calls `fetch_image`.
    # easiest is to mock `pick_image_sfw` for higher level test.
    with patch("fetch.pick_safebooru.pick_image_sfw", new_callable=AsyncMock) as m:
        yield m

@pytest.fixture
def mock_process_image():
    with patch("fetch.pick_safebooru.process_image", new_callable=AsyncMock) as m:
        yield m

@pytest.mark.asyncio
async def test_pick_media_sfw_success(mock_fetch_image, mock_process_image, seen_set):
    mock_fetch_image.return_value = (("http://url.com/img.jpg", "md5", "site"), FetchError.NONE)
    mock_process_image.return_value = (MagicMock(), "img.jpg", None)
    
    res = await pick_media_sfw("tags", seen_set)
    
    assert res[5] == FetchError.NONE
    assert res[0] == "http://url.com/img.jpg"

@pytest.mark.asyncio
async def test_pick_media_sfw_all_failure(mock_fetch_image, mock_process_image, seen_set):
    mock_fetch_image.return_value = (None, FetchError.NO_RESULTS)
    
    res = await pick_media_sfw("tags", seen_set)
    
    assert res[5] == FetchError.NO_RESULTS
    assert res[0] is None
