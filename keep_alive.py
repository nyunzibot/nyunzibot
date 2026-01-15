import os
import logging
from aiohttp import web

log = logging.getLogger(__name__)

async def health_check(request):
    return web.Response(text="OK")

async def start_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Railway provides PORT, default to 8080 or another safe port logic
    port = int(os.environ.get("PORT", 8080))
    
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"Health check server running on port {port}")
