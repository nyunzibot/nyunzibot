
import pytest
from tags.tag_builder import build_tag_ladder
from tags.tag_sets import BASE_TAG_OPTIONS, ALLOWED_OVERRIDES
from text.plap_lines import PLAP_LINES_INTIMATE_NATURAL
from text.succ_lines import SUCC_LINES_INTIMATE

def test_tag_sets_integrity():
    assert len(BASE_TAG_OPTIONS) > 0
    assert len(ALLOWED_OVERRIDES) > 0

def test_text_lines_integrity():
    assert isinstance(PLAP_LINES_INTIMATE_NATURAL, list)
    assert isinstance(SUCC_LINES_INTIMATE, list)
    assert len(PLAP_LINES_INTIMATE_NATURAL) > 0
    assert len(SUCC_LINES_INTIMATE) > 0

def test_build_tag_ladder():
    """Test building tag ladder."""
    base = "base"
    positives = ["pos1", "pos2"]
    
    # Mock random to ensure deterministic behavior for index checks
    import random
    from unittest.mock import patch
    
    with patch("random.sample", side_effect=lambda pop, k: pop[:k]), \
         patch("random.choice", side_effect=lambda s: s[0] if s else None):

        # Test standard build
        ladder = build_tag_ladder(base, positives, negative_tags=None)
        
        # Verify structure
        assert len(ladder) > 0
        # If random is mocked, we can check basic containment
        assert any(base in s for s in ladder)
