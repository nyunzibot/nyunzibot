import logging
import sys

def setup_logging():
    # Railway-friendly logging: stdout for INFO, stderr for ERROR
    # This prevents Railway from marking all logs as "error"
    
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    
    # Handler for INFO and below -> stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(lambda record: record.levelno < logging.ERROR)
    stdout_handler.setFormatter(formatter)
    
    # Handler for ERROR and above -> stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)
    
    log = logging.getLogger("nyunzi")
    log.info("Process boot ✅")
    return log
