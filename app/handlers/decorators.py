# app/execution/decorators.py
import logging
import aiohttp
import time
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

def handler(action_name: str):
    """Декоратор для регистрации хендлера"""
    def decorator(cls):
        cls._action_name = action_name
        return cls
    return decorator

def retry(max_attempts: int = 3, delay: float = 1.0):
    """Декоратор для повторных попыток"""
    def decorator(cls):
        cls._retries = max_attempts - 1  # -1 потому что первая попытка не считается retry
        cls._retry_delay = delay
        return cls
    return decorator

def timeout(seconds: float):
    """Декоратор для таймаута выполнения"""
    def decorator(cls):
        cls._timeout = seconds
        return cls
    return decorator

def validate_payload(*required_fields):
    """Декоратор для валидации полей в payload"""
    def decorator(cls):
        original_validate = cls.validate_input
        
        async def validate_with_fields(self, task):
            # Проверяем обязательные поля
            for field in required_fields:
                if not hasattr(task, 'payload') or field not in task.payload:
                    logger.error(f"Missing required field: {field}")
                    return False
                if not task.payload[field]:
                    logger.error(f"Empty required field: {field}")
                    return False
            
            # Вызываем оригинальную валидацию
            return await original_validate(self, task)
        
        cls.validate_input = validate_with_fields
        return cls
    return decorator

def log_execution(log_level: int = logging.INFO):
    """Декоратор для логирования выполнения"""
    def decorator(cls):
        original_call = cls.__call__
        
        async def logged_call(self, task, profile=None):
            profile_id = getattr(profile, 'profile_id', 'unknown') if profile else 'none'
            logger.log(log_level, f"Starting handler {self.name} for profile {profile_id}")
            start_time = time.time()
            
            try:
                result = await original_call(self, task, profile)
                execution_time = time.time() - start_time
                
                if isinstance(result, dict) and not result.get("success", True):
                    logger.error(f"Handler {self.name} failed in {execution_time:.2f}s: {result.get('error', 'Unknown error')}")
                else:
                    logger.log(log_level, f"Handler {self.name} completed in {execution_time:.2f}s")
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"Handler {self.name} crashed in {execution_time:.2f}s: {e}")
                raise
        
        cls.__call__ = logged_call
        return cls
    return decorator
