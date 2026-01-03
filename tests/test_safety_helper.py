import sys
from unittest.mock import MagicMock
sys.modules["nudenet"] = MagicMock()

import unittest
import io
import os
from unittest.mock import patch
from fetch.pick_safebooru import _check_safety_with_temp_file

class TestSafetyHelper(unittest.TestCase):
    @patch('fetch.pick_safebooru.check_is_safe')
    def test_bytesio_handling(self, mock_check):
        mock_check.return_value = False # Unsafe
        
        # Create BytesIO
        data = b"image data"
        bio = io.BytesIO(data)
        mock_file = MagicMock()
        mock_file.fp = bio
        
        # Test
        is_safe = _check_safety_with_temp_file(mock_file, "test.jpg")
        
        # Should be False because mock says False
        self.assertFalse(is_safe)
        
        # Check was called
        mock_check.assert_called_once()
        args = mock_check.call_args[0]
        temp_path = args[0]
        
        # Temp file should be deleted by now?
        # The finally block deletes it.
        # But we can verify it WAS a file path string
        self.assertIsInstance(temp_path, str)
        self.assertTrue(temp_path.endswith(".jpg"))
        
        # Verify file is gone
        self.assertFalse(os.path.exists(temp_path))

    @patch('fetch.pick_safebooru.check_is_safe')
    def test_video_skip(self, mock_check):
        # Video should return True immediately without check
        mock_file = MagicMock()
        is_safe = _check_safety_with_temp_file(mock_file, "movie.mp4")
        self.assertTrue(is_safe)
        mock_check.assert_not_called()

if __name__ == '__main__':
    unittest.main()
