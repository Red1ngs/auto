# app/execution/handlers_manager.py
import logging
from typing import Dict, Optional

from app.execution.interfaces.base_handler import BaseHandler

logger = logging.getLogger(__name__)       

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