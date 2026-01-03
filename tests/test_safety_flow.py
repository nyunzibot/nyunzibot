import sys
from unittest.mock import MagicMock

# MOCK NudeNet BEFORE IMPORTING application modules
sys.modules["nudenet"] = MagicMock()

import unittest
from unittest.mock import patch, AsyncMock
from fetch.pick_safebooru import pick_media_sfw, FetchError

class TestSafety(unittest.IsolatedAsyncioTestCase):
    @patch('fetch.pick_safebooru.fetch_image', new_callable=AsyncMock)
    @patch('fetch.pick_safebooru.process_image', new_callable=AsyncMock)
    @patch('fetch.pick_safebooru.check_is_safe')
    async def test_unsafe_image_skipped(self, mock_check, mock_process, mock_fetch):
        # Setup: fetch returns a URL
        mock_fetch.return_value = ("http://example.com/bad.jpg", "md5bad", "gelbooru")
        
        # Setup: process returns a file (mock)
        mock_file = MagicMock()
        mock_file.fp.name = "temp/bad.jpg"
        mock_process.return_value = (mock_file, "bad.jpg", None)
        
        # Setup: check_is_safe returns False (UNSAFE)
        mock_check.return_value = False
        
        # Action
        res = await pick_media_sfw("tags", set(), tries=2)
        
        # Assert: Should return None or fail, because it kept hitting unsafe images
        self.assertEqual(res[5], FetchError.NO_RESULTS)
        self.assertEqual(mock_check.call_count, 2)
        mock_file.fp.close.assert_called()

    @patch('fetch.pick_safebooru.fetch_image', new_callable=AsyncMock)
    @patch('fetch.pick_safebooru.process_image', new_callable=AsyncMock)
    @patch('fetch.pick_safebooru.check_is_safe')
    async def test_safe_image_accepted(self, mock_check, mock_process, mock_fetch):
        mock_fetch.return_value = ("http://example.com/good.jpg", "md5good", "gelbooru")
        mock_file = MagicMock()
        mock_file.fp.name = "temp/good.jpg"
        mock_process.return_value = (mock_file, "good.jpg", None)
        
        # SAFE
        mock_check.return_value = True
        
        res = await pick_media_sfw("tags", set(), tries=1)
        
        # Should return success
        self.assertEqual(res[5], FetchError.NONE)
        self.assertEqual(res[4], "good.jpg")

if __name__ == '__main__':
    unittest.main()
