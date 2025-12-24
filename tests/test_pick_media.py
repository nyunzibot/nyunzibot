import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fetch.pick import pick_media, FetchError
from images.process import ProcessError

# Helpers
@pytest.fixture
def seen_set():
    return set()

@pytest.fixture
def mock_fetch_image():
    with patch("fetch.pick.pick_image", new_callable=AsyncMock) as m:
        yield m

@pytest.fixture
def mock_process_image():
    with patch("fetch.pick.process_image", new_callable=AsyncMock) as m:
        yield m

@pytest.fixture
def mock_is_video_url():
    with patch("fetch.pick._is_video_url") as m:
        m.return_value = False
        yield m

@pytest.mark.asyncio
async def test_pick_media_success(mock_fetch_image, mock_process_image, seen_set):
    # Setup
    mock_fetch_image.return_value = (("http://url.com/img.jpg", "md5hash", "danbooru"), FetchError.NONE)
    mock_process_image.return_value = (MagicMock(), "img.jpg", None) # File, fname, error
    
    # Run
    res = await pick_media("tags", seen_set)
    
    # Assert
    assert res[5] == FetchError.NONE # Error should be NONE
    assert res[0] == "http://url.com/img.jpg"
    assert res[3] is not None # File object
    # Success returns early, caller adds to seen. pick_media does not add it on success.
    assert "md5hash" not in seen_set

@pytest.mark.asyncio
async def test_pick_media_rate_limited(mock_fetch_image, mock_process_image, seen_set):
    mock_fetch_image.return_value = (("http://url.com/img.jpg", "md5hash", "danbooru"), FetchError.NONE)
    mock_process_image.return_value = (None, None, ProcessError.RATE_LIMITED)
    
    res = await pick_media("tags", seen_set)
    
    # RATE_LIMITED returns early
    assert res[5] == FetchError.RATE_LIMITED
    assert res[0] is None
    assert "md5hash" not in seen_set

@pytest.mark.asyncio
async def test_pick_media_download_failed_retry_success(mock_fetch_image, mock_process_image, seen_set):
    mock_fetch_image.return_value = (("http://url.com/img.jpg", "md5hash", "danbooru"), FetchError.NONE)
    
    # First call: Download Failed
    # Second call: Success
    mock_process_image.side_effect = [
        (None, None, ProcessError.DOWNLOAD_FAILED),
        (MagicMock(), "img.jpg", None)
    ]
    
    res = await pick_media("tags", seen_set)
    
    assert res[5] == FetchError.NONE
    assert mock_process_image.call_count == 2
    # Retry success returns early
    assert "md5hash" not in seen_set

@pytest.mark.asyncio
async def test_pick_media_download_failed_retry_fail(mock_fetch_image, mock_process_image, seen_set):
    mock_fetch_image.return_value = (("http://url.com/img.jpg", "md5hash", "danbooru"), FetchError.NONE)
    
    # First call: Download Failed
    # Second call: Download Failed
    # This should trigger "trying different image" -> loop -> mock_fetch called again
    
    # Actually, let's make it fetch a *new* image on second loop
    mock_fetch_image.side_effect = [
        (("http://url.com/img1.jpg", "md5_1", "site"), FetchError.NONE),
        (("http://url.com/img2.jpg", "md5_2", "site"), FetchError.NONE)
    ]
    
    mock_process_image.side_effect = [
        (None, None, ProcessError.DOWNLOAD_FAILED), # Img1 attempt 1
        (None, None, ProcessError.DOWNLOAD_FAILED), # Img1 attempt 2 (retry)
        (MagicMock(), "img2.jpg", None)             # Img2 attempt 1 (success)
    ]
    
    res = await pick_media("tags", seen_set, tries=2)
    
    assert res[5] == FetchError.NONE
    assert res[0] == "http://url.com/img2.jpg"
    # md5_1 should be in seen_set because we attempted it and failed
    assert "md5_1" in seen_set 
    # md5_2 succeeded, so it is NOT in seen_set
    assert "md5_2" not in seen_set

@pytest.mark.asyncio
async def test_pick_media_processing_failed_compress_success(mock_fetch_image, mock_process_image, seen_set):
    mock_fetch_image.return_value = (("http://url.com/img.jpg", "md5", "site"), FetchError.NONE)
    
    # 1. Processing failed
    # 2. Retry with compression -> Success
    mock_process_image.side_effect = [
        (None, None, ProcessError.PROCESSING_FAILED),
        (MagicMock(), "img.jpg", None)
    ]
    
    res = await pick_media("tags", seen_set)
    
    assert res[5] == FetchError.NONE
    # Verify second call had aggressive_compress=True
    args, kwargs = mock_process_image.call_args_list[1]
    assert kwargs.get("aggressive_compress") is True

@pytest.mark.asyncio
async def test_pick_media_video_too_large_fallback(mock_fetch_image, mock_process_image, mock_is_video_url, seen_set):
    mock_fetch_image.return_value = (("http://url.com/video.mp4", "md5", "site"), FetchError.NONE)
    mock_is_video_url.return_value = True
    
    # 1. File too large
    # 2. Compression attempt -> Still too large (or None returned)
    mock_process_image.side_effect = [
        (None, None, ProcessError.FILE_TOO_LARGE),
        (None, None, ProcessError.FILE_TOO_LARGE)
    ]
    
    res = await pick_media("tags", seen_set)
    
    # Expect: Return URL, no file, Error NONE
    assert res[5] == FetchError.NONE
    assert res[0] == "http://url.com/video.mp4"
    assert res[3] is None # No file
