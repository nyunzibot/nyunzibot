import random
import asyncio
import aiohttp
import re
import logging
from config import RULE34VIDEO_URL
from .common import is_supported_file_url

log = logging.getLogger("nyunzi")

# Regex to find video links from search page
# href="https://rule34video.com/video/3510828/terasu-fan-animation/"
RE_VIDEO_LINK = re.compile(r'href="(https?://rule34video\.com/video/\d+/[^"]+)"')

# Regex to find video source URL on view page
# contentUrl in JSON-LD schema: "contentUrl": "https://rule34video.com/get_file/.../...mp4/"
RE_CONTENT_URL = re.compile(r'"contentUrl":\s*"(https?://[^"]+\.mp4[^"]*)"')
# video_url in flashvars: video_url: 'function/0/https://rule34video.com/get_file/.../...mp4/...'
RE_FLASHVARS_URL = re.compile(r"video_url:\s*'function/0/(https?://[^']+\.mp4[^']*)'")
# get_file download link as fallback
RE_GET_FILE = re.compile(r'href="(https?://rule34video\.com/get_file/[^"]+\.mp4[^"]*)"')


async def fetch_image_rule34video(tags: str, avoid_md5s: set[str]) -> tuple[str, str | None, str] | None:
    """
    Scraper-based fetcher for Rule34Video.com.
    Returns video URLs (primarily MP4).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": f"{RULE34VIDEO_URL}/",
    }
    
    MAX_ATTEMPTS = 3
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for attempt in range(MAX_ATTEMPTS):
            # Pick a random page (1 to ~5 pages deep)
            page_num = random.randint(1, 5)
            
            # Search URL format
            search_url = f"{RULE34VIDEO_URL}/search/?q={tags}&page={page_num}"
            html = ""
            
            try:
                async with session.get(search_url, timeout=15) as resp:
                    if resp.status != 200:
                        log.info(f"[R34VID] Search failed: {resp.status}")
                        continue
                    html = await resp.text()
            except Exception as e:
                log.warning(f"[R34VID] Search error: {e}")
                continue
            
            # Extract video page links
            links = list(set(RE_VIDEO_LINK.findall(html)))
            if not links:
                log.info(f"[R34VID] No videos found for tags={tags} page={page_num}")
                continue
            
            log.info(f"[R34VID] Found {len(links)} video links on page {page_num}")
            
            random.shuffle(links)
            
            for video_page_url in links[:5]:  # Try up to 5 videos per search
                try:
                    async with session.get(video_page_url, timeout=15) as resp:
                        if resp.status != 200:
                            continue
                        view_html = await resp.text()
                except Exception:
                    continue
                
                # Extract video source URL
                # Priority: contentUrl (JSON-LD) > flashvars > get_file links
                media_url = None
                
                # 1. Try contentUrl from JSON-LD schema
                m_content = RE_CONTENT_URL.search(view_html)
                if m_content:
                    media_url = m_content.group(1)
                
                # 2. Try flashvars video_url
                if not media_url:
                    m_flash = RE_FLASHVARS_URL.search(view_html)
                    if m_flash:
                        media_url = m_flash.group(1)
                
                # 3. Fall back to get_file download links
                if not media_url:
                    get_files = RE_GET_FILE.findall(view_html)
                    if get_files:
                        # Prefer 720p if available
                        for gf in get_files:
                            if "720" in gf:
                                media_url = gf
                                break
                        if not media_url:
                            media_url = get_files[0]
                
                if not media_url:
                    continue
                
                # Clean up URL (remove HTML entities, query params, trailing slashes)
                media_url = media_url.replace("&amp;", "&")
                # Remove query params for file extension validation
                # But keep the original URL for downloading
                clean_url = media_url.split("?")[0].rstrip("/")
                
                if not is_supported_file_url(clean_url):
                    continue
                
                # Try to extract something like MD5 from URL (video ID as fallback)
                md5 = None
                # Extract video ID from original URL as a unique identifier
                vid_match = re.search(r'/video/(\d+)/', video_page_url)
                if vid_match:
                    md5 = f"r34vid_{vid_match.group(1)}"
                
                if md5 and md5 in avoid_md5s:
                    continue
                
                log.info(f"[R34VID] Picked {media_url[:80]}... (id={md5})")
                return (media_url, md5, "rule34video")
    
    return None
