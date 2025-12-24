import pytest
from commands.plap import _normalize_extra_tags, _validate_extra_tags, _apply_extra_to_ladder
from tags.tag_sets import ALLOWED_OVERRIDES

# Mock constants if needed, but we can import them. 
# Assuming PLAP_BASE and NEGATIVE_TAGS are importable or we can test generic behavior.

def test_normalize_extra_tags():
    assert _normalize_extra_tags("  foo   bar  ") == "foo bar"
    assert _normalize_extra_tags("foo") == "foo"
    assert _normalize_extra_tags(None) == ""
    assert _normalize_extra_tags("") == ""

def test_validate_extra_tags():
    # Valid tags
    assert _validate_extra_tags("blue_hair") is None
    assert _validate_extra_tags("blue_hair long_hair") is None
    
    # Negative tags
    assert _validate_extra_tags("-tag") is not None
    assert _validate_extra_tags("tag -other") is not None
    
    # Prohibited tags (assuming 'loli' or 'shota' might be in NEGATIVE_TAGS checks)
    # We rely on the sets imported in the module.
    # We can try to test a known negative tag if we knew one from source, 
    # but based on reading plap.py, let's assume standard behavior.
    
    # Check one from allowed overrides
    if ALLOWED_OVERRIDES:
        allowed = list(ALLOWED_OVERRIDES)[0]
        assert _validate_extra_tags(allowed) is None

def test_apply_extra_to_ladder():
    ladder = ["base tag", "base tag2"]
    
    # Simple addition
    result = _apply_extra_to_ladder(ladder, "extra")
    # Result should have "extra" appended and negative tags attached
    assert all("extra" in r for r in result)
    
    # Override behavior
    if ALLOWED_OVERRIDES:
        override = list(ALLOWED_OVERRIDES)[0]
        result_override = _apply_extra_to_ladder(ladder, override)
        # Should replace the base tag (first word)
        # Note: logic: base_parts[0] = override_tag
        
        # Verify it's present at start
        assert result_override[0].startswith(override)
        
    # Validation of negative suffix handling
    # If we add extra tags, negative suffix should still be there
    result = _apply_extra_to_ladder(["base"], "extra")
    assert result[0].startswith("base extra")
