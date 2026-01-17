import asyncio
import logging
import os
from fetch.preselected import fetch_post_by_id
from images.process import process_image

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nyunzi")

async def test_ugoira():
    # Test Item: 119199250 (Ugoira)
    print("--- Testing fetch_post_by_id for Ugoira ---")
    results = await fetch_post_by_id(119199250, site="pixiv")
    
    if not results:
        print("FAIL: No results returned.")
        return
        
    url, md5 = results[0]
    print(f"URL: {url}")
    print(f"MD5: {md5}")
    
    if not url.startswith("file://"):
        print("FAIL: Expected file:// URL")
        return
        
    print("--- Testing process_image with local file ---")
    file_obj, filename, error = await process_image(url, spoiler=False)
    
    if file_obj:
        print(f"SUCCESS: Processed file {filename}")
        print(f"Size: {file_obj.fp.getbuffer().nbytes} bytes")
        file_obj.fp.close()
    else:
        print(f"FAIL: process_image failed with error {error}")

    # Clean up the temp file created by converter
    local_path = url[7:]
    if os.name == 'nt' and local_path.startswith('/') and ':' in local_path:
        local_path = local_path.lstrip('/')
    
    if os.path.exists(local_path):
        print(f"Cleaning up {local_path}")
        try:
             os.unlink(local_path)
        except Exception as e:
            print(f"Cleanup error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ugoira())
