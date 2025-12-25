import random
import asyncio
import aiohttp
import re
import logging
from config import RULE34US_URL
from .common import is_supported_file_url

log = logging.getLogger("nyunzi")

# Regex to find post IDs from alt="Image: NNNNN"
RE_IMAGE_ID = re.compile(r'alt="Image:\s*(\d+)"')

# Regex to find post link pattern: ?r=posts/view&id=NNNNN
RE_POST_LINK = re.compile(r'\?r=posts/view&amp;id=(\d+)')
RE_POST_LINK_2 = re.compile(r'\?r=posts/view&id=(\d+)')

# Regex to find the image/video URL on the view page
# Example: <img src="..." id="image-container" ...> OR <source src="..." ...>
RE_IMAGE_SRC = re.compile(r'id="current-image-container".*?src="([^"]+)"', re.DOTALL)
RE_VIDEO_SRC = re.compile(r'<source[^>]*src="([^"]+)"')
# Also try: <img src="https://img.rule34.us/..." id="originalImage"
RE_ORIGINAL_IMG = re.compile(r'id="originalImage"[^>]*src="([^"]+)"')


async def fetch_image_rule34us(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    """
    Scraper-based fetcher for Rule34.us.
    Uses the correct URL pattern: ?r=posts/index&q=...
    """
    # Browser-like headers are essential
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": f"{RULE34US_URL}/",
    }
    
    # Rule34.us uses page number (1, 2, 3...) not pid offset
    MAX_ATTEMPTS = 4
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for attempt in range(MAX_ATTEMPTS):
            # Pick a random page (1 to ~10 pages deep)
            page_num = random.randint(1, 10)
            
            # Correct URL format: ?r=posts/index&q=tags
            search_url = f"{RULE34US_URL}/index.php?r=posts/index&q={tags}&page={page_num}"
            html = ""
            
            try:
                async with session.get(search_url, timeout=15) as resp:
                    if resp.status != 200:
                        log.info(f"[R34US] Search failed: {resp.status} {search_url}")
                        continue
                    html = await resp.text()
            except Exception as e:
                log.warning(f"[R34US] Search error: {e}")
                continue
            
            # Extract post IDs from alt="Image: NNNN" patterns
            ids = set(RE_IMAGE_ID.findall(html))
            # Also try link patterns
            ids |= set(RE_POST_LINK.findall(html))
            ids |= set(RE_POST_LINK_2.findall(html))
            
            if not ids:
                log.info(f"[R34US] No posts found for tags={tags} page={page_num}")
                continue
                
            # Pick a random ID from this page
            id_list = list(ids)
            random.shuffle(id_list)
            
            for post_id in id_list:
                # Fetch view page using correct format
                view_url = f"{RULE34US_URL}/index.php?r=posts/view&id={post_id}"
                
                try:
                    async with session.get(view_url, timeout=15) as resp:
                        if resp.status != 200:
                            continue
                        view_html = await resp.text()
                except Exception:
                    continue
                
                # Extract media URL
                media_url = None
                
                # Check for video source first
                m_vid = RE_VIDEO_SRC.search(view_html)
                if m_vid:
                    media_url = m_vid.group(1)
                else:
                    # Check for original image
                    m_orig = RE_ORIGINAL_IMG.search(view_html)
                    if m_orig:
                        media_url = m_orig.group(1)
                    else:
                        # Try image container
                        m_img = RE_IMAGE_SRC.search(view_html)
                        if m_img:
                            media_url = m_img.group(1)
                
                if not media_url:
                    log.debug(f"[R34US] No media URL found for post {post_id}")
                    continue
                
                # Fix relative URLs
                if media_url.startswith("//"):
                    media_url = "https:" + media_url
                elif media_url.startswith("/"):
                    base = RULE34US_URL.rstrip("/")
                    media_url = base + media_url
                elif not media_url.startswith("http"):
                    media_url = f"{RULE34US_URL}/{media_url}"

                if not is_supported_file_url(media_url):
                    continue
                
                # Try to extract MD5 from URL
                # Typical pattern: .../images/xx/xx/md5.ext or just .../md5.ext
                md5 = None
                fname = media_url.split("/")[-1]
                possible_md5 = fname.split(".")[0]
                if len(possible_md5) == 32 and all(c in "0123456789abcdefABCDEF" for c in possible_md5):
                    md5 = possible_md5
                
                if md5 and md5 in avoid_md5s:
                    continue
                    
                # Normalize CDN URLs to non-CDN versions (fixes DNS issues on some hosts)
                # video-cdn1.rule34.us -> video.rule34.us
                # img-cdn1.rule34.us -> img.rule34.us
                media_url = re.sub(r'video-cdn\d*\.rule34\.us', 'video.rule34.us', media_url)
                media_url = re.sub(r'img-cdn\d*\.rule34\.us', 'img.rule34.us', media_url)
                    
                log.info(f"[R34US] Picked {media_url} (md5={md5})")
                return (media_url, md5, "rule34us")

    return None
