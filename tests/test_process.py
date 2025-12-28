
import pytest
import discord # Needed for discord.File reference
from unittest.mock import MagicMock, AsyncMock, patch
from images.process import process_image, ProcessError
import io

@pytest.fixture
def mock_aiohttp_stream():
    with patch("aiohttp.ClientSession") as m:
        session = AsyncMock()
        session.get = MagicMock()
        
        response = AsyncMock()
        response.status = 200
        # Default read valid small image
        valid_gif = b'GIF87a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        response.read.return_value = valid_gif
        
        session.get.return_value.__aenter__.return_value = response
        m.return_value.__aenter__.return_value = session
        yield m

@pytest.fixture
def mock_file_ops():
    with patch("builtins.open", new_callable=MagicMock) as m_open:
        m_file = MagicMock()
        m_open.return_value.__enter__.return_value = m_file
        with patch("os.stat") as m_stat:
            m_stat.return_value.st_size = 1024
            with patch("os.makedirs"):
                with patch("os.remove"):
                    yield m_open

@pytest.mark.asyncio
async def test_process_image_success(mock_aiohttp_stream, mock_file_ops):
    url = "http://example.com/image.gif"
    file, fname, error = await process_image(url)
    assert error == ProcessError.NONE
    assert fname == "action.gif"

@pytest.mark.asyncio
async def test_process_image_download_failed(mock_aiohttp_stream, mock_file_ops):
    session = mock_aiohttp_stream.return_value.__aenter__.return_value
    response = session.get.return_value.__aenter__.return_value
    response.status = 404
    
    url = "http://example.com/404.jpg"
    file, fname, error = await process_image(url)
    
    assert error == ProcessError.DOWNLOAD_FAILED

@pytest.mark.asyncio
async def test_process_image_too_large(mock_aiohttp_stream, mock_file_ops):
    session = mock_aiohttp_stream.return_value.__aenter__.return_value
    response = session.get.return_value.__aenter__.return_value
    
    # Needs to be > 25MB (25_000_000)
    # Using 26MB string
    large_data = b"0" * (26 * 1024 * 1024)
    response.read.return_value = large_data
    
    url = "http://example.com/large.jpg"
    file, fname, error = await process_image(url)
    
    assert error == ProcessError.FILE_TOO_LARGE

@pytest.mark.asyncio
async def test_process_video_compress_success(mock_aiohttp_stream, mock_file_ops):
    with patch("os.stat") as m_stat:
        m_stat.side_effect = [
            MagicMock(st_size=30*1024*1024),
            MagicMock(st_size=10*1024*1024)
        ]
        with patch("images.process.compress_video", new_callable=AsyncMock) as m_compress:
            m_compress.return_value = discord.File(io.BytesIO(b"video"), filename="vid.mp4")
            
            url = "http://example.com/video.mp4"
            session = mock_aiohttp_stream.return_value.__aenter__.return_value
            response = session.get.return_value.__aenter__.return_value
            # > MAX_DISCORD but <= MAX_DOWNLOAD
            response.read.return_value = b"0" * (26 * 1024 * 1024)
            
            file, fname, error = await process_image(url, aggressive_compress=True)
            
            assert error == ProcessError.NONE
            assert m_compress.called
