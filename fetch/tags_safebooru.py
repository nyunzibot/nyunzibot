"""
Safebooru tag autocomplete module.
Fetches tag suggestions from Safebooru API for SFW commands.
"""

import aiohttp
import logging
import time
from typing import List, Dict, Tuple
from config import USER_AGENT
from discord import app_commands

log = logging.getLogger("nyunzi")

# Cache structure: {prefix: (timestamp, [results])}
_TAG_CACHE: Dict[str, Tuple[float, List[app_commands.Choice[str]]]] = {}
CACHE_TTL = 300  # 5 minutes


async def fetch_tag_suggestions_safebooru(current: str) -> List[app_commands.Choice[str]]:
    """
    Fetch tag suggestions from Safebooru API based on the current input.
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
    cache_key = f"safebooru:{query}"
    now = time.time()
    if cache_key in _TAG_CACHE:
        ts, cached_choices = _TAG_CACHE[cache_key]
        if now - ts < CACHE_TTL:
            return _rebuild_choices(base_prefix, cached_choices)

    # API Request - Safebooru uses different API endpoint
    url = "https://safebooru.org/autocomplete.php"
    params = {
        "q": query,
    }

    try:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    return []
                
                data = await resp.json(content_type=None)
                
                # Safebooru autocomplete returns a list of dicts with 'label' and 'value'
                choices = []
                if isinstance(data, list):
                    for t in data:
                        if isinstance(t, dict):
                            # Safebooru format: {"label": "tag_name (count)", "value": "tag_name"}
                            label = t.get("label", "")
                            value = t.get("value", "")
                            if value:
                                choices.append(app_commands.Choice(name=label, value=value))
                        elif isinstance(t, str):
                            # Simple string format
                            choices.append(app_commands.Choice(name=t, value=t))
                
                # Cache the raw choices for this query word
                _TAG_CACHE[cache_key] = (now, choices)
                
                return _rebuild_choices(base_prefix, choices)

    except Exception as e:
        log.warning(f"[TAGS_SAFE] Error fetching tags for '{query}': {e}")
        return []


def _rebuild_choices(base_prefix: str, choices: List[app_commands.Choice[str]]) -> List[app_commands.Choice[str]]:
    """
    Reconstruct valid choices by prepending the already-typed tags.
    """
    if not base_prefix:
        return choices[:25]
    
    final_choices = []
    for c in choices:
        full_value = f"{base_prefix} {c.value}"
        full_name = f"{base_prefix} {c.name}"
        
        # Truncate if too long (max 100 chars)
        if len(full_name) > 100:
             full_name = full_name[:97] + "..."
        if len(full_value) > 100:
             full_value = full_value[:100]
             
        final_choices.append(app_commands.Choice(name=full_name, value=full_value))
    
    return final_choices[:25]
