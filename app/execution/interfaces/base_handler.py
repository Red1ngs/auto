# файл: app/execution/interfaces/base_handler.py
"""
Базовый интерфейс и шаблон поведения всех хендлеров
"""
from abc import ABC, abstractmethod
import time
import asyncio
import logging

from app.models.execution_models import ProfileTask
from app.utils.logging_utils import measure_time

logger = logging.getLogger(__name__)

class BaseHandler(ABC):
    """Базовый интерфейс и шаблон поведения всех хендлеров"""

    def __init__(self):
        self.name = getattr(self.__class__, '_action_name', self.__class__.__name__.lower())
        self.retries = getattr(self.__class__, '_retries', 0)
        self.retry_delay = getattr(self.__class__, '_retry_delay', 1.0)
        self.timeout = getattr(self.__class__, '_timeout', None)

    @abstractmethod
    async def execute(self, task: ProfileTask) -> dict:
        pass

    async def validate_input(self, task: ProfileTask) -> bool:
        return True

    async def cleanup(self, task: ProfileTask):
        pass

    async def handle_error(self, task: ProfileTask, error: Exception) -> dict:
        logger.error(f"Handler {self.name} failed: {error}")
        return {"success": False, "error": str(error), "handler": self.name}

    async def __call__(self, task: ProfileTask) -> dict:
        start_time = time.time()

        try:
            if not await self.validate_input(task):
                return {"success": False, "error": "Input validation failed", "handler": self.name}

            result = await self._execute_with_features(task)

            if isinstance(result, dict):
                result["_handler"] = self.name
                result["_execution_time"] = measure_time(start_time)
                result.setdefault("success", True)
            else:
                result = {
                    "success": True,
                    "data": result,
                    "_handler": self.name,
                    "_execution_time": measure_time(start_time)
                }

            return result

        except Exception as e:
            return await self.handle_error(task, e)
        finally:
            await self.cleanup(task)

    async def _execute_with_features(self, task: ProfileTask):
        for attempt in range(self.retries + 1):
            try:
                if self.timeout:
                    return await asyncio.wait_for(self.execute(task), timeout=self.timeout)
                return await self.execute(task)
            except Exception as e:
                if attempt < self.retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Handler {self.name} attempt {attempt + 1} failed: {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                raise
