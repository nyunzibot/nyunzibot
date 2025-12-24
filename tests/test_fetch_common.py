import pytest
from fetch.common import is_supported_file_url, size_ok, should_lower_limit, pid_max_for

def test_is_supported_file_url():
    # Valid extensions
    assert is_supported_file_url("http://example.com/image.jpg")
    assert is_supported_file_url("https://example.com/image.jpeg")
    assert is_supported_file_url("https://example.com/image.png")
    assert is_supported_file_url("https://example.com/image.webp")
    assert is_supported_file_url("https://example.com/image.gif")
    assert is_supported_file_url("https://example.com/video.mp4")
    assert is_supported_file_url("https://example.com/video.webm")
    
    # Capitalization shouldn't matter
    assert is_supported_file_url("https://example.com/image.JPG")
    
    # Invalid extensions
    assert not is_supported_file_url("https://example.com/file.pdf")
    assert not is_supported_file_url("https://example.com/image.bmp")
    
    # Not a URL
    assert not is_supported_file_url("not_a_url.jpg")
    assert not is_supported_file_url("")
    assert not is_supported_file_url(None)

def test_size_ok():
    # Valid ranges (700-9000)
    assert size_ok(800, 800)
    assert size_ok(700, 700)
    assert size_ok(9000, 9000)
    
    # Only one dim valid? Function logic says AND check for < 700?
    # Logic is: if width < 700 or height < 700: return False
    assert not size_ok(699, 800)
    assert not size_ok(800, 699)
    
    # Too large
    # Logic is: if width > 9000 or height > 9000: return False
    assert not size_ok(9001, 800)
    assert not size_ok(800, 9001)
    
    # None values
    assert size_ok(None, None)
    assert size_ok(800, None) # code says `if width is None or height is None: return True`

def test_should_lower_limit():
    # Known failure codes
    assert should_lower_limit(429, None, False)
    assert should_lower_limit(500, None, False)
    assert should_lower_limit(400, None, False)
    
    # Parsing failure
    assert should_lower_limit(200, None, True)
    
    # Exception present
    assert should_lower_limit(200, Exception("fail"), False)
    
    # OK status
    assert not should_lower_limit(200, None, False)
    assert not should_lower_limit(404, None, False) # 404 isn't in the list

def test_pid_max_for():
    # Gelbooru
    assert pid_max_for("gelbooru", "score:>50") == 1
    assert pid_max_for("gelbooru", "score:>20") == 4
    assert pid_max_for("gelbooru", "other") == 5
    
    # Rule34
    assert pid_max_for("rule34", "score:>50") == 1
    assert pid_max_for("rule34", "other") == 5
