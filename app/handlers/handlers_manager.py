# app/execution/handlers_manager.py

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional

from app.models.execution_models import ProfileTask

logger = logging.getLogger(__name__)

class BaseHandler(ABC):
    """Базовый класс для всех хендлеров"""
    
    def __init__(self):
        self.name = getattr(self.__class__, '_action_name', self.__class__.__name__.lower())
        self.retries = getattr(self.__class__, '_retries', 0)
        self.retry_delay = getattr(self.__class__, '_retry_delay', 1.0)
        self.timeout = getattr(self.__class__, '_timeout', None)
    
    @abstractmethod
    async def execute(self, task: ProfileTask) -> dict:
        """Основная логика хендлера"""
        pass
    
    async def validate_input(self, task: ProfileTask) -> bool:
        """Валидация входных данных"""
        return True
    
    async def cleanup(self, task: ProfileTask):
        """Очистка ресурсов"""
        pass
    
    async def handle_error(self, task: ProfileTask, error: Exception) -> dict:
        """Обработка ошибок"""
        logger.error(f"Handler {self.name} failed: {error}")
        return {"success": False, "error": str(error), "handler": self.name}
    
    async def __call__(self, task: ProfileTask) -> dict:
        """Основной метод вызова с поддержкой всех декораторов"""
        start_time = time.time()
         
        try:
            # Валидация
            if not await self.validate_input(task):
                return {"success": False, "error": "Input validation failed", "handler": self.name}
            
            # Выполнение с повторами и таймаутом
            result = await self._execute_with_features(task)
            
            # Добавляем метаданные если результат это dict
            if isinstance(result, dict):
                result["_handler"] = self.name
                result["_execution_time"] = time.time() - start_time
                if "success" not in result:
                    result["success"] = True
            else:
                # Если результат не dict, оборачиваем
                result = {
                    "success": True,
                    "data": result,
                    "_handler": self.name,
                    "_execution_time": time.time() - start_time
                }
            
            return result
            
        except Exception as e:
            return await self.handle_error(task, e)
        finally:
            await self.cleanup(task)
    
    async def _execute_with_features(self, task: ProfileTask):
        """Выполнение с поддержкой retry и timeout"""
        last_exception = None
        
        for attempt in range(self.retries + 1):
            try:
                if self.timeout:
                    return await asyncio.wait_for(
                        self.execute(task), 
                        timeout=self.timeout
                    )
                else:
                    return await self.execute(task)
                    
            except Exception as e:
                last_exception = e
                if attempt < self.retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Handler {self.name} attempt {attempt + 1} failed: {last_exception}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                raise e


class HttpHandler(BaseHandler):
    """Базовый класс для HTTP операций"""
    
    async def cleanup(self, task: ProfileTask):
        """Автоматически закрываем HTTP соединение"""
        try:
            profile = task.profile
            if profile and hasattr(profile, 'http_service') and profile.http_service:
                await profile.http_service.close_client()
        except Exception as e:
            logger.warning(f"HTTP cleanup failed: {e}")

class FileHandler(BaseHandler):
    """Базовый класс для файловых операций"""
    
    def __init__(self, base_path: str = "./"):
        super().__init__()
        self.base_path = base_path
        

class HandlersManager:
    """Менеджер для автоматической регистрации хендлеров"""
    
    def __init__(self):
        self._handlers: Dict[str, BaseHandler] = {}
    
    def register_handler(self, handler_instance: BaseHandler):
        """Зарегистрировать экземпляр хендлера"""
        if not isinstance(handler_instance, BaseHandler):
            raise ValueError("Handler must be instance of BaseHandler")
        
        action_name = handler_instance.name
        self._handlers[action_name] = handler_instance
        logger.info(f"Registered handler for action: {action_name}")
    
    def register_handlers_from_module(self, module):
        """Автоматически зарегистрировать все хендлеры из модуля"""
        import inspect
        
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BaseHandler) and 
                obj != BaseHandler and
                not inspect.isabstract(obj)):
                
                # Создаём экземпляр и регистрируем
                handler_instance = obj()
                self.register_handler(handler_instance)
    
    def get_handler(self, action_name: str) -> Optional[BaseHandler]:
        """Получить хендлер по имени действия"""
        return self._handlers.get(action_name)
    
    def get_all_handlers(self) -> Dict[str, BaseHandler]:
        """Получить все зарегистрированные хендлеры"""
        return self._handlers.copy()

# Глобальный экземпляр менеджера
handlers_manager: HandlersManager = HandlersManager()