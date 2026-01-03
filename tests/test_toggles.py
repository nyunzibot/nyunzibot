import unittest
from unittest.mock import patch, AsyncMock
import config
from fetch import fetch_image

class TestToggles(unittest.IsolatedAsyncioTestCase):
    @patch('fetch.fetch_image.fetch_image_gelbooru', new_callable=AsyncMock)
    @patch('fetch.fetch_image.fetch_image_rule34', new_callable=AsyncMock)
    async def test_disable_gelbooru(self, mock_r34, mock_gel):
        # Setup mocks
        mock_gel.return_value = None
        mock_r34.return_value = None

        # Ensure defaults
        config.ENABLE_GELBOORU = True
        config.ENABLE_RULE34 = True

        # Case 1: Gelbooru Enabled
        await fetch_image.fetch_image("tags", set())
        mock_gel.assert_called_once()
        mock_r34.assert_called() # Should call next since gel returned None

        # Reset
        mock_gel.reset_mock()
        mock_r34.reset_mock()
        
        # Case 2: Gelbooru Disabled
        config.ENABLE_GELBOORU = False
        await fetch_image.fetch_image("tags", set())
        
        mock_gel.assert_not_called()
        mock_r34.assert_called()

if __name__ == '__main__':
    unittest.main()
