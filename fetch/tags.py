import aiohttp
import asyncio
import logging
import time
from typing import List, Dict, Tuple
from config import GELBOORU_API_KEY, GELBOORU_USER_ID, USER_AGENT
from discord import app_commands
from tags.tag_sets import NEGATIVE_TAGS, ALLOWED_OVERRIDES

log = logging.getLogger("nyunzi")

# Cache structure: {prefix: (timestamp, [results])}
_TAG_CACHE: Dict[str, Tuple[float, List[app_commands.Choice[str]]]] = {}
CACHE_TTL = 300  # 5 minutes

# Pre-process negative tags into a set for fast lookup
_BLOCKED_TAGS = {t.lstrip("-") for t in NEGATIVE_TAGS.split()} - ALLOWED_OVERRIDES

async def fetch_tag_suggestions(current: str) -> List[app_commands.Choice[str]]:
    """
    Fetch tag suggestions from Gelbooru API based on the current input.
    Handles partial words by querying for the last word in the input string.
    """
    current = current.strip()
    if not current:
        return []

    # Split input to find the actual tag being typed (the last one)
    parts = current.split(" ")
    base_prefix = " ".join(parts[:-1])
    query = parts[-1]

    if not query or len(query) < 2:
        return []

    # Check cache
    now = time.time()
    if query in _TAG_CACHE:
        ts, cached_choices = _TAG_CACHE[query]
        if now - ts < CACHE_TTL:
            return _rebuild_choices(base_prefix, cached_choices)

    # API Request
    url = "https://gelbooru.com/index.php"
    params = {
        "page": "dapi",
        "s": "tag",
        "q": "index",
        "json": "1",
        "limit": "25",
        "name_pattern": f"{query}%",
        "orderby": "count" 
    }
    
    # Pass auth if available (usually not strictly needed for tags, but good practice)
    if GELBOORU_API_KEY and GELBOORU_USER_ID:
        params["api_key"] = GELBOORU_API_KEY
        params["user_id"] = GELBOORU_USER_ID

    try:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    return []
                
                data = await resp.json(content_type=None)
                
                # Gelbooru JSON for tags is usually a list of dicts, or a dict with 'tag' key
                # It can be inconsistent.
                tags = []
                if isinstance(data, list):
                    tags = data
                elif isinstance(data, dict):
                    # sometimes wrapped in distinct wrapper
                    tags = data.get("tag", [])
                
                choices = []
                for t in tags:
                    if isinstance(t, dict):
                        name = t.get("name")
                        count = t.get("count", 0)
                        if name:
                            # Filter out blocked tags
                            if name.lower() in _BLOCKED_TAGS:
                                continue

                            # Format: "tag_name (12k)"
                            label = f"{name} ({format_count(count)})"
                            choices.append(app_commands.Choice(name=label, value=name))
                
                # Cache the raw choices for this query word
                _TAG_CACHE[query] = (now, choices)
                
                return _rebuild_choices(base_prefix, choices)

    except Exception as e:
        log.warning(f"[TAGS] Error fetching tags for '{query}': {e}")
        return []

def _rebuild_choices(base_prefix: str, choices: List[app_commands.Choice[str]]) -> List[app_commands.Choice[str]]:
    """
    Reconstruct valid choices by prepending the already-typed tags.
    """
    if not base_prefix:
        return choices
    
    final_choices = []
    for c in choices:
        # Value becomes "tag1 tag2 new_tag"
        full_value = f"{base_prefix} {c.value}"
        # Name becomes "tag1 tag2 new_tag (count)" - usually too long, so maybe just show the new part in name?
        # But Discord UI shows Name. If we change Name, it might be confusing.
        # Standard pattern: Name shows full state or just the suggestion.
        # Let's try showing just the new tag in name, but value is full.
        # WAIIIIT. If user selects it, it replaces the WHOLE field.
        # So name MUST represent what they see? No, Name is what they click. Value is what is filled.
        # If I type "blue h", and select "hair", the field becomes "hair" IF returned value is just "hair".
        # So Value MUST be "blue hair".
        
        # UI wise:
        # Input: "blue h"
        # Choice Name: "hair (500k)" -> User clicks -> Input: "blue hair"
        # Choice Name: "blue hair" -> User clicks -> Input: "blue hair"
        
        # Better UX: Show the full string in name so they know context?
        # Or Just the new tag. "hair (500k)" looks cleaner.
        # BUT if I return just "hair", the client replaces "blue h" with "hair".
        # Result: "hair". "blue" is lost. 
        # CORRECT: Value must be the FULL string.
        
        full_name = f"{base_prefix} {c.name}"
        # Truncate if too long (max 100 chars)
        if len(full_name) > 100:
             full_name = full_name[:97] + "..."
             
        final_choices.append(app_commands.Choice(name=full_name, value=full_value))
    
    return final_choices

def format_count(count):
    try:
        c = int(count)
        if c >= 1000000: return f"{c/1000000:.1f}M"
        if c >= 1000: return f"{c/1000:.1f}k"
        return str(c)
    except:
        return "0"
