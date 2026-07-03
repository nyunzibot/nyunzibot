
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fetch.safebooru import fetch_image_safebooru
from fetch.gelbooru import fetch_image_gelbooru
from fetch.rule34 import fetch_image_rule34

@pytest.fixture(autouse=True)
def mock_config(monkeypatch):
    monkeypatch.setattr("fetch.gelbooru.GELBOORU_API_KEY", "dummy")
    monkeypatch.setattr("fetch.gelbooru.GELBOORU_USER_ID", "dummy")
    monkeypatch.setattr("fetch.rule34.RULE34_API_KEY", "dummy")
    monkeypatch.setattr("fetch.rule34.RULE34_USER_ID", "dummy")

@pytest.fixture
def mock_aiohttp():
    with patch("aiohttp.ClientSession") as m:
        session = AsyncMock()
        # session.get needs to be a MagicMock (sync callable) that returns an AsyncMock (the CM)
        # Because we do `async with session.get(...)`, not `await session.get(...)`
        cm = AsyncMock()
        session.get = MagicMock(return_value=cm) 
        m.return_value.__aenter__.return_value = session
        yield session

@pytest.fixture
def avoid_set():
    return set()

@pytest.mark.asyncio
async def test_safebooru_fetch_success(mock_aiohttp, avoid_set):
    # Safebooru: text() -> json()
    xml_resp = MagicMock()
    xml_resp.text = AsyncMock()
    xml_resp.text.return_value = '<posts count="100" offset="0"></posts>'
    xml_resp.status = 200
    
    json_resp = MagicMock()
    json_resp.json = AsyncMock()
    json_resp.json.return_value = [
        {"image": "img.jpg", "directory": "dir", "hash": "md5", "score": 100}
    ]
    json_resp.status = 200
    
    cm = mock_aiohttp.get.return_value
    cm.__aenter__.side_effect = [xml_resp, json_resp]
    
    res = await fetch_image_safebooru("tags", avoid_set)
    assert res is not None

@pytest.mark.asyncio
async def test_gelbooru_fetch_success(mock_aiohttp, avoid_set):
    # Gelbooru: json() (probe) -> json() (fetch)
    # The code probes with json=1 first
    probe_resp = MagicMock()
    probe_resp.json = AsyncMock()
    probe_resp.json.return_value = {"@attributes": {"count": 50}}
    probe_resp.status = 200
    
    fetch_resp = MagicMock()
    fetch_resp.json = AsyncMock()
    fetch_resp.json.return_value = {
        "post": [{"file_url": "http://img.url/image.jpg", "md5": "md5", "score": 10, "width": 1000, "height": 1000}]
    }
    fetch_resp.status = 200
    
    cm = mock_aiohttp.get.return_value
    cm.__aenter__.side_effect = [probe_resp, fetch_resp]
    
    res = await fetch_image_gelbooru("tags", avoid_set)
    assert res is not None

@pytest.mark.asyncio
async def test_rule34_fetch_success(mock_aiohttp, avoid_set):
    # Rule34: text() -> text() (Step 1 probe -> Step 2 fetch)
    # Rule34 03 logic: text() probe, text() fetch.
    # Note: rule34.py implies multiple strategies. Default calls fetch_image_rule34 (strategy 3 usually or logic?)
    # fetch/rule34.py: uses XML.
    
    xml_resp = MagicMock()
    xml_resp.text = AsyncMock()
    xml_resp.text.return_value = '<posts count="20" offset="0"></posts>'
    xml_resp.status = 200
    
    # Needs a post in the second xml
    xml_resp2 = MagicMock()
    xml_resp2.text = AsyncMock()
    xml_resp2.text.return_value = '<posts count="20"><post file_url="http://r34.url/img.jpg" md5="md5" width="1000" height="1000"/></posts>'
    xml_resp2.status = 200
    
    cm = mock_aiohttp.get.return_value
    cm.__aenter__.side_effect = [xml_resp, xml_resp2]
    
    res = await fetch_image_rule34("tags", avoid_set)
    assert res is not None

@pytest.mark.asyncio
async def test_fetch_no_results(mock_aiohttp, avoid_set):
    xml_resp = MagicMock()
    xml_resp.text = AsyncMock() # Safebooru uses text
    xml_resp.text.return_value = '<posts count="0" offset="0"></posts>'
    xml_resp.status = 200
    
    cm = mock_aiohttp.get.return_value
    cm.__aenter__.return_value = xml_resp
    
    res = await fetch_image_safebooru("tags", avoid_set)
    assert res is None
