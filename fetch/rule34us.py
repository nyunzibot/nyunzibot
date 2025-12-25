import random
import asyncio
import aiohttp
import re
import logging
from config import RULE34US_URL
from .common import is_supported_file_url

log = logging.getLogger("nyunzi")

# Regex to find post IDs on the list page
# href="index.php?page=post&s=view&id=12345"
RE_POST_LINK = re.compile(r'index\.php\?page=post&amp;s=view&amp;id=(\d+)')
# Also try unencoded & just in case
RE_POST_LINK_2 = re.compile(r'index\.php\?page=post&s=view&id=(\d+)')

# Regex to find the image/video URL on the view page
# <img src="..." id="image" ...> OR <source src="..." ...>
RE_IMAGE_SRC = re.compile(r'id="image"[^>]*src="([^"]+)"')
RE_VIDEO_SRC = re.compile(r'<source[^>]*src="([^"]+)"')

# Regex to try and find MD5 (heuristic: often in stats or just not available easily)
# On rule34.us view page: "Md5: ..." text?
# Let's rely on URL/random for now, MD5 might be harder to robustly scrape without full parser.
# We'll return None for MD5 if we can't find it easily.


async def fetch_image_rule34us(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    """
    Scraper-based fetcher for Rule34.us.
    This site often returns HTML even on API endpoints or has Cloudflare.
    We'll try to scrape the HTML interface.
    """
    # Browser-like headers are essential
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": f"{RULE34US_URL}/",
    }
    
    # Try a few pages of results
    # Rule34.us pages are by PID (page index? or offset? Usually pid=0, 42, 84 assuming 42 per page)
    # Let's try random pid steps.
    
    LIMIT = 42 # Default posts per page on many boorus
    MAX_ATTEMPTS = 4
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for attempt in range(MAX_ATTEMPTS):
            # Pick a random page offset (0 to ~10 pages deep)
            pid = random.randint(0, 10) * LIMIT
            
            search_url = f"{RULE34US_URL}/index.php?page=post&s=list&tags={tags}&pid={pid}"
            html = ""
            
            try:
                async with session.get(search_url, timeout=10) as resp:
                    if resp.status != 200:
                        log.info(f"[R34US] Search failed: {resp.status} {search_url}")
                        continue
                    html = await resp.text()
            except Exception as e:
                log.warning(f"[R34US] Search error: {e}")
                continue
            
            # Extract post IDs
            ids = set(RE_POST_LINK.findall(html)) | set(RE_POST_LINK_2.findall(html))
            if not ids:
                log.info(f"[R34US] No posts found for tags={tags} pid={pid}")
                continue
                
            # Pick a random ID from this page
            id_list = list(ids)
            random.shuffle(id_list)
            
            for post_id in id_list:
                # Fetch view page
                view_url = f"{RULE34US_URL}/index.php?page=post&s=view&id={post_id}"
                
                try:
                    async with session.get(view_url, timeout=10) as resp:
                        if resp.status != 200:
                            continue
                        view_html = await resp.text()
                except Exception:
                    continue
                
                # Extract media URL
                # Video source takes precedence?
                media_url = None
                
                # Check for video source
                m_vid = RE_VIDEO_SRC.search(view_html)
                if m_vid:
                    media_url = m_vid.group(1)
                else:
                    # Check for image source
                    m_img = RE_IMAGE_SRC.search(view_html)
                    if m_img:
                        media_url = m_img.group(1)
                
                if not media_url:
                    continue
                
                # Relative URL?
                if media_url.startswith("//"):
                    media_url = "https:" + media_url
                elif media_url.startswith("/"):
                    # relative to root?
                    # check if RULE34US_URL ends with /
                    base = RULE34US_URL.rstrip("/")
                    media_url = base + media_url
                elif not media_url.startswith("http"):
                    # Relative to current path? rare but possible
                    media_url = f"{RULE34US_URL}/{media_url}"

                if not is_supported_file_url(media_url):
                    continue
                
                # Try to extract valid MD5?
                # Usually impossible to reliably get MD5 from just scraping easily without structured data
                # We'll use the post ID or URL as a proxy for "seen" if needed, but the caller expects MD5.
                # Let's fake an MD5 or leave it None? 
                # System generally expects MD5 for stats. 
                # Rule34.us image URLs might contain md5: 
                # e.g. https://img.rule34.us/images/25/0a/250a... .jpg -> 250a... is often md5
                # Let's try to extract from URL
                
                # Typical pattern: .../images/xx/xx/md5.ext or just .../md5.ext
                # Let's try to grab a 32-char hex string from the filename
                md5 = None
                # split by / get last part
                fname = media_url.split("/")[-1]
                # split by . get first part
                possible_md5 = fname.split(".")[0]
                if len(possible_md5) == 32 and all(c in "0123456789abcdefABCDEF" for c in possible_md5):
                    md5 = possible_md5
                
                if md5 and md5 in avoid_md5s:
                    continue
                    
                log.info(f"[R34US] Picked {media_url} (md5={md5})")
                return (media_url, md5, "rule34us")

    return None
