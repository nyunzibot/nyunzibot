import random
from tags.preselected import PRESELECTED_SFW

def fetch_preselected(category: str, avoid_md5s: set[str]) -> tuple[list[str], str, str] | None:
    """
    Tries to pick a random URL (or list of URLs) from the pre-selected list for the given category.
    Returns (urls, md5, site) if found and not in avoid list.
    - urls: list of image URLs (single image = list of one)
    - md5: We use a hash of the URL(s) for deduplication
    - site: "preselected"
    """
    if not category or category not in PRESELECTED_SFW:
        return None
        
    items = PRESELECTED_SFW[category]
    if not items:
        return None
    
    # Filter out ones we've seen (using first URL or the URL itself as pseudo-md5)
    candidates = []
    for item in items:
        if isinstance(item, list):
            # It's a group of URLs - use first URL as the identifier
            if item and item[0] not in avoid_md5s:
                candidates.append(item)
        else:
            # Single URL
            if item not in avoid_md5s:
                candidates.append([item])  # Wrap in list for consistent return type
    
    if not candidates:
        return None
        
    picked = random.choice(candidates)
    
    # Use first URL as the md5/identifier for deduplication
    md5 = picked[0] if picked else ""
    
    # Return format: (urls, md5, site)
    return (picked, md5, "preselected")

