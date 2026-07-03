import logging
import os
import re
import sys


class SecretRedactingFilter(logging.Filter):
    """
    Scrubs sensitive values from log messages before they reach any handler.

    Catches:
      - Discord bot tokens  (3-part dot-separated base64)
      - Long hex strings    (≥32 hex chars, typical API keys)
      - Any runtime secret  loaded from known env vars
    """

    # Discord token pattern: base64.base64.base64
    _DISCORD_TOKEN_RE = re.compile(
        r"[A-Za-z0-9_\-]{24,}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}"
    )
    # Long hex API key (≥32 hex chars)
    _HEX_KEY_RE = re.compile(r"[0-9a-fA-F]{32,}")

    # Env vars whose values should be redacted if they appear in logs
    _SECRET_ENV_VARS = [
        "TOKEN",
        "RULE34_API_KEY",
        "RULE34_USER_ID",
        "GELBOORU_API_KEY",
        "GELBOORU_USER_ID",
        "KONACHAN_API_KEY",
        "KONACHAN_LOGIN_ID",
        "DANBOORU_API_KEY",
        "DANBOORU_LOGIN_ID",
        "PIXIV_REFRESH_TOKEN",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
    ]

    def __init__(self):
        super().__init__()
        # Build a set of non-empty secret values to scrub at runtime
        self._secret_values: list[str] = []
        for var in self._SECRET_ENV_VARS:
            val = os.getenv(var, "")
            if val and len(val) >= 4:  # only worth redacting if non-trivial
                self._secret_values.append(val)

    def _redact(self, message: str) -> str:
        # 1. Redact known secret values (longest first to avoid partial matches)
        for secret in sorted(self._secret_values, key=len, reverse=True):
            if secret in message:
                message = message.replace(secret, "[REDACTED]")

        # 2. Redact Discord token patterns
        message = self._DISCORD_TOKEN_RE.sub("[REDACTED_TOKEN]", message)

        # 3. Redact long hex keys
        message = self._HEX_KEY_RE.sub("[REDACTED_KEY]", message)

        return message

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        # Also redact args if they're strings (for %-style formatting)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def setup_logging():
    # Railway-friendly logging: stdout for INFO, stderr for ERROR
    # This prevents Railway from marking all logs as "error"

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Shared redaction filter — scrubs secrets from all log output
    redactor = SecretRedactingFilter()

    # Handler for INFO and below -> stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(lambda record: record.levelno < logging.ERROR)
    stdout_handler.addFilter(redactor)
    stdout_handler.setFormatter(formatter)

    # Handler for ERROR and above -> stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.addFilter(redactor)
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
