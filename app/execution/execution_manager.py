# app/execution/executor_manager.py
import asyncio
from typing import Optional, Dict, Any, Callable

from app.execution.cluster_executor import ClusterExecutor
from app.models.execution_models import ProfileTask

from app.proxy.proxy_manager import ProxyManager


class ExecutorManager:
    """Глобальный менеджер выполнения задач"""
    
    _instance: Optional['ExecutorManager'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._executor = ClusterExecutor()
            self._proxy_manager = ProxyManager()
            self._initialized = True
    
    @property
    def executor(self) -> ClusterExecutor:
        """Получить экземпляр ClusterExecutor"""
        return self._executor
    
    # Удобные методы-обертки
    async def setup_profile(self, profile_id: str, base_delay: float = 1.0):
        """
        Назначить лучший прокси профилю и подключить его в HTTP-клиент.

        Args:
            profile_id: ID профиля
            base_delay: базовая задержка для кластера
        """
        if not self._proxy_manager:
            raise RuntimeError("ProxyManager is not set in ExecutorManager")

        # Получаем список всех доступных прокси
        all_proxy_ids = [str(p.id) for p in self._proxy_manager.all]

        # Выбираем лучший по загруженности
        best_proxy_id = await self._executor.select_best_proxy_id(all_proxy_ids)
        if not best_proxy_id:
            raise RuntimeError("Нет доступных прокси")

        # Назначаем профиль в кластер
        await self._executor.add_profile_to_proxy(profile_id, best_proxy_id, base_delay)
    
    async def run_task(self, task: ProfileTask, timeout: Optional[float] = None):
        """Выполнить задачу и получить результат"""
        return await self._executor.execute_task(task.profile_id, task, timeout)
    
    async def schedule_task(self, task: ProfileTask) -> asyncio.Future:
        """Запланировать задачу и получить Future"""
        return await self._executor.execute_task(task.profile_id, task)
    
    def register_handler(self, action: str, handler: Callable):
        """Зарегистрировать обработчик действия"""
        self._executor.register_action_handler(action, handler)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получить полную статистику"""
        return await self._executor.get_all_stats()
    
    async def shutdown(self):
        """Корректно завершить работу"""
        await self._executor.shutdown()

# Глобальный экземпляр
executor_manager = ExecutorManager()