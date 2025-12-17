import logging

def setup_logging():
    # Railway-friendly logging (same settings as original)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    log = logging.getLogger("nyunzi")
    log.info("Process boot ✅")
    return log
