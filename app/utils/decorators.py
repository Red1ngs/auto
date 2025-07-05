# utils/decorators.py
import logging
import time
import requests
from functools import wraps
from typing import Callable, TypeVar, ParamSpec, cast
import functools

from schemas.exceptions import AppError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

P = ParamSpec("P")
R = TypeVar("R")

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

def handle_app_errors(raise_on_fail: bool = False):
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except AppError as e:
                logger.error(f"[{e.__class__.__name__}] {e} (code={e.code})")
                if e.on_error:
                    try:
                        return e.on_error()
                    except Exception as inner:
                        logger.exception(f"[on_error failed] {inner}")
                if raise_on_fail:
                    raise
            except Exception as ex:
                logger.exception(f"Unexpected error in {func.__name__}: {ex}")
                raise
        return cast(Callable[P, R], wrapper)
    return decorator