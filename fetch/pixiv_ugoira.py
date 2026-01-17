import logging
import zipfile
import io
import tempfile
import os
import aiohttp
from PIL import Image

log = logging.getLogger("nyunzi")

async def convert_ugoira_to_gif(api, illust_id: int) -> str | None:
    """
    Downloads Ugoira metadata and zip content, converts to GIF, 
    and returns absolute path to temporary GIF file.
    
    The caller is responsible for deleting the file after use.
    """
    try:
        # 1. Get Metadata
        log.info(f"[UGOIRA] Fetching metadata for {illust_id}")
        meta_json = await api.ugoira_metadata(illust_id)
        if not meta_json or 'ugoira_metadata' not in meta_json:
            log.warning("[UGOIRA] No ugoira_metadata found")
            return None
        
        meta = meta_json['ugoira_metadata']
        zip_url = meta['zip_urls']['medium'] # Use medium for reasonable size
        frames_info = meta['frames']
        
        # 2. Download ZIP
        log.info(f"[UGOIRA] Downloading ZIP: {zip_url}")
        headers = {"Referer": "https://www.pixiv.net/"}
        
        zip_data = None
        # We need a fresh session or reuse one if not provided. 
        # api.client is available but specialized for API calls. 
        # Using aiohttp directly for file download is safer/easier here.
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(zip_url) as resp:
                if resp.status != 200:
                    log.warning(f"[UGOIRA] Download failed: {resp.status}")
                    return None
                zip_data = await resp.read()
                
        if not zip_data:
            return None
            
        # 3. Extract and Process Frames
        log.info(f"[UGOIRA] Processing {len(frames_info)} frames...")
        
        images = []
        durations = []
        
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            for frame in frames_info:
                fname = frame['file']
                delay = frame['delay']
                
                with zf.open(fname) as f:
                    # Load image
                    img_data = f.read()
                    img = Image.open(io.BytesIO(img_data)).convert("RGBA")
                    images.append(img)
                    durations.append(delay)
        
        if not images:
            return None
            
        # 4. Save as GIF
        # Calculate average duration if variable? GIF supports variable, but check PIL support.
        # PIL save takes 'duration' as int or list/tuple of ints.
        
        temp_gif = tempfile.NamedTemporaryFile(suffix=".gif", delete=False)
        temp_gif_path = temp_gif.name
        temp_gif.close()
        
        log.info(f"[UGOIRA] Saving GIF to {temp_gif_path}")
        
        # Optimize?
        # Resize if huge?
        first_img = images[0]
        if first_img.width > 600:
            ratio = 600 / first_img.width
            new_size = (600, int(first_img.height * ratio))
            log.info(f"[UGOIRA] Resizing from {first_img.size} to {new_size}")
            
            resized_images = []
            for img in images:
                resized_images.append(img.resize(new_size, Image.Resampling.LANCZOS))
            images = resized_images
        
        images[0].save(
            temp_gif_path,
            save_all=True,
            append_images=images[1:],
            format="GIF",
            duration=durations,
            loop=0,
            optimize=True
        )
        
        size = os.path.getsize(temp_gif_path)
        log.info(f"[UGOIRA] Created GIF: {size} bytes")
        
        return temp_gif_path
        
    except Exception as e:
        log.error(f"[UGOIRA] Conversion failed: {e}", exc_info=True)
        return None
