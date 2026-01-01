import random
from tags.preselected import PRESELECTED_SFW

def fetch_preselected(category: str, avoid_md5s: set[str]) -> tuple[str, str, str] | None:
    """
    Tries to pick a random URL from the pre-selected list for the given category.
    Returns (url, md5, site) if found and not in avoid list.
    We use the URL itself as the MD5 for deduplication purposes.
    """
    if not category or category not in PRESELECTED_SFW:
        return None
        
    urls = PRESELECTED_SFW[category]
    if not urls:
        return None
        
    # Filter out ones we've engaged with (using URL as pseudo-md5)
    # We create a shuffled list to try
    candidates = [u for u in urls if u not in avoid_md5s]
    
    if not candidates:
        return None
        
    picked_url = random.choice(candidates)
    
    # Return format: (url, md5, site)
    # 'site' is 'preselected' so we can track stats if needed
    return (picked_url, picked_url, "preselected")
