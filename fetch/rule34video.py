import re
import logging
import random
import aiohttp
from config import RULE34VIDEO_URL
from fetch.common import is_supported_file_url

log = logging.getLogger("nyunzi")

async def fetch_image_rule34video(tags, avoid_md5s):
    """
    Scrape rule34video.com search results.
    We need to scrape because there is no known public API.
    
    Strategy:
    1. Search for tags (random page).
    2. Extract video page links and DURATION from search results.
    3. Filter out videos > 3 minutes.
    4. Randomly pick a video page.
    5. Fetch video page and extract 'contentUrl' (JSON-LD) or 'video_url' (flashvars).
    """
    
    # regex to find video pages in search results
    RE_ITEM_URL = re.compile(r'href="(https?://rule34video\.com/video/\d+/[^"]+)"')
    RE_ITEM_TIME = re.compile(r'<div class="time">([\d:]+)</div>')
    
    # regex to find video source in video page
    RE_CONTENT_URL = re.compile(r'"contentUrl":\s*"(https?://[^"]+\.mp4[^"]*)"')
    RE_FLASHVARS_URL = re.compile(r"video_url:\s*'function/0/(https?://[^']+\.mp4[^']*)'")
    RE_GET_FILE = re.compile(r'href="(https?://rule34video\.com/get_file/[^"]+\.mp4[^"]*)"')
    
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
            
            # Search page extraction
            log.info(f"[R34VID] Searching page {page_num} for tags: {tags}")
            try:
                async with session.get(search_url, timeout=15) as resp:
                    if resp.status != 200:
                        log.warning(f"[R34VID] Failed to fetch search page: {resp.status}")
                        continue
                    
                    html = await resp.text()
            except Exception as e:
                log.warning(f"[R34VID] Search error: {e}")
                continue
            
            # Parse items from search page
            # Split by item container to keep URL and Time together
            raw_items = html.split('<div class="item thumb')
            
            valid_links = []
            
            for item_html in raw_items[1:]: # Skip preamble
                # Extract URL
                url_match = RE_ITEM_URL.search(item_html)
                if not url_match:
                    continue
                url = url_match.group(1)
                
                # Extract Duration
                time_match = RE_ITEM_TIME.search(item_html)
                if time_match:
                    time_str = time_match.group(1)
                    try:
                        parts = list(map(int, time_str.split(':')))
                        duration = 0
                        if len(parts) == 2: # MM:SS
                            duration = parts[0] * 60 + parts[1]
                        elif len(parts) == 3: # HH:MM:SS
                            duration = parts[0] * 3600 + parts[1] * 60 + parts[2]
                        
                        # FILTER: Max 3 minutes (180 seconds)
                        if duration > 180:
                            # log.debug(f"Skipping video {url} (duration {time_str})")
                            continue
                    except ValueError:
                        pass # Parsing failed, include it anyway
                
                valid_links.append(url)
            
            if not valid_links:
                log.info(f"[R34VID] No matching videos (<= 3 mins) found on page {page_num}")
                continue
            
            log.info(f"[R34VID] Found {len(valid_links)} valid video links (<= 3 mins) on page {page_num}")
            
            random.shuffle(valid_links)
            
            for video_page_url in valid_links[:5]:  # Try up to 5 videos per search
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
                
                log.info(f"[R34VID] Picked {media_url} (id={md5})")
                return (media_url, md5, "rule34video")
    
    return None
