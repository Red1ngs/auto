import logging
import aiohttp
import asyncio

from typing import Callable, TypeVar, ParamSpec
from functools import wraps

logger = logging.getLogger(__name__)
P = ParamSpec("P")
R = TypeVar("R")

def log_http_request(method: str = "GET"):
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def wrapper(self, url: str, payload=None, *args, retries: int = 3, timeout: float = 360.0, **kwargs):
            logger.info(f"[{method}] → URL: {url}")
            logger.debug(f"[{method}] Headers: {self.headers}")
            logger.debug(f"[{method}] Cookies: {self.cookie}")
            if payload is not None:
                logger.debug(f"[{method}] Payload (JSON): {payload}")

            for attempt in range(1, retries + 1):
                try:
                    response = await func(
                        self, url, payload,
                        *args,
                        retries=retries,
                        timeout=timeout,
                        **kwargs
                    )
                    if response is not None:
                        logger.info(f"[{method}] ← Response status: {response.status}")
                        return response
                except aiohttp.ClientError as ex:
                    logger.warning(f"[{attempt}/{retries}] {method} request error: {ex}")
                    await asyncio.sleep(5)

            logger.error(f"[{method}] Failed after {retries} attempts → {url}")
            return None

        return wrapper  # type: ignore
    return decorator
