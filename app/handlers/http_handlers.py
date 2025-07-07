import logging
import time
import requests
from functools import wraps
from typing import Callable


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def log_http_request(method: str = "GET"):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, url: str, payload=None, *args, retries: int = 3, timeout: float = 360.0, **kwargs):
            logger.info(f"[{method}] → URL: {url}")
            logger.debug(f"[{method}] Headers: {self.headers}")
            logger.debug(f"[{method}] Cookies: {self.cookie}")
            if payload is not None:
                logger.debug(f"[{method}] Payload (JSON): {payload}")

            for attempt in range(1, retries + 1):
                try:
                    response = func(
                        self, url, payload,
                        *args,
                        retries=retries,
                        timeout=timeout,
                        **kwargs
                    )
                    if response is not None:
                        logger.info(f"[{method}] ← Response status: {response.status_code}")
                        logger.debug(f"[{method}] Response content (up to 300 chars): {response.text[:300]}")
                    return response
                except requests.RequestException as ex:
                    logger.warning(f"[{attempt}/{retries}] {method} request error: {ex}")
                    time.sleep(5)

            logger.error(f"[{method}] Failed after {retries} attempts → {url}")
            return None

        return wrapper
    return decorator