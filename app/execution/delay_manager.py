# app/execution/delay_manager.py
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime
import logging

from app.models.execution_models import (
    ProxyDelayState, DelayConfig, TaskPriority, ProfileTask
)

logger = logging.getLogger(__name__)

class DelayManager:
    """Централизованный менеджер задержек с поддержкой приоритетов"""
    
    def __init__(self, config: Optional[DelayConfig] = None):
        self._proxy_delays: Dict[str, ProxyDelayState] = {}
        self._config = config or DelayConfig()
        self._lock = asyncio.Lock()
        
        # Отслеживание последних задач по приоритетам для каждого прокси
        self._last_priority_execution: Dict[str, Dict[TaskPriority, datetime]] = {}
    
    async def get_delay_for_profile(self, profile_id: str, proxy_id: str,
                               task: Optional[ProfileTask] = None) -> float:
        """Получить задержку для профиля с учетом прокси и приоритета"""
        async with self._lock:
            proxy_state = self._proxy_delays.get(proxy_id)
            if not proxy_state:
                proxy_state = ProxyDelayState(proxy_id=proxy_id)
                self._proxy_delays[proxy_id] = proxy_state

            # Добавить профиль к активным, если его там нет
            if profile_id not in proxy_state.active_profiles:
                proxy_state.active_profiles.append(profile_id)

            # Базовая задержка прокси
            base_proxy_delay = proxy_state.base_delay if self._config.enable_profile_delay else proxy_state.current_delay

            # Количество активных профилей на прокси
            active_profiles_count = len(proxy_state.active_profiles)

            # Задержка на профиль = базовая задержка прокси / количество профилей
            delay_per_profile = base_proxy_delay / active_profiles_count if active_profiles_count > 0 else base_proxy_delay

            # Множитель приоритета
            priority_multiplier = 1.1
            if task and task.priority in self._config.priority_multipliers:
                priority_multiplier = self._config.priority_multipliers[task.priority]

            # Дополнительная задержка для соблюдения минимальных интервалов между задачами
            additional_delay = 2.0
            if task:
                additional_delay = await self._calculate_priority_delay(proxy_id, task.priority)

            # Итоговая задержка
            total_delay = (delay_per_profile * priority_multiplier) + additional_delay
            total_delay = max(0.1, min(total_delay, self._config.max_delay))

            # Для критических задач минимальная задержка
            if task and task.priority == TaskPriority.CRITICAL:
                total_delay = min(total_delay, 0.5)

            logger.debug(
                f"Delay for profile {profile_id} on proxy {proxy_id}: "
                f"base_proxy_delay={base_proxy_delay}s, active_profiles={active_profiles_count}, "
                f"delay_per_profile={delay_per_profile}s, priority={priority_multiplier}, "
                f"additional={additional_delay}s, total={total_delay}s"
            )

            return total_delay
        
    async def set_proxy_base_delay(self, proxy_id: str, base_delay: float):
        """Установить базовую задержку для прокси"""
        async with self._lock:
            proxy_state = self._proxy_delays.get(proxy_id)
            if not proxy_state:
                proxy_state = ProxyDelayState(proxy_id=proxy_id)
                self._proxy_delays[proxy_id] = proxy_state
            proxy_state.base_delay = base_delay
            logger.info(f"Set base delay for proxy {proxy_id} to {base_delay}s")

    
    async def _calculate_priority_delay(self, proxy_id: str, priority: TaskPriority) -> float:
        """Рассчитать дополнительную задержку на основе приоритета"""
        if proxy_id not in self._last_priority_execution:
            self._last_priority_execution[proxy_id] = {}
        
        priority_history = self._last_priority_execution[proxy_id]
        now = datetime.now()
        
        # Минимальные интервалы между задачами разных приоритетов
        min_intervals = {
            TaskPriority.CRITICAL: 0.1,
            TaskPriority.HIGH: 0.5,
            TaskPriority.NORMAL: 1.0,
            TaskPriority.LOW: 2.0,
            TaskPriority.BACKGROUND: 5.0
        }
        
        min_interval = min_intervals.get(priority, 1.0)
        
        # Проверить, когда последний раз выполнялась задача этого приоритета
        last_execution = priority_history.get(priority)
        if last_execution:
            time_since_last = (now - last_execution).total_seconds()
            if time_since_last < min_interval:
                return min_interval - time_since_last
        
        return 0.0
    
    async def record_request_result(self, profile_id: str, proxy_id: str,
                               success: bool, task: Optional[ProfileTask] = None,
                               error_type: Optional[str] = None):
        """Записать результат запроса для адаптации задержек"""
        async with self._lock:
            proxy_state = self._proxy_delays.get(proxy_id)
            if not proxy_state:
                return

            proxy_state.last_request_time = datetime.now()

            # Обновить историю выполнения по приоритетам
            if task:
                if proxy_id not in self._last_priority_execution:
                    self._last_priority_execution[proxy_id] = {}
                self._last_priority_execution[proxy_id][task.priority] = datetime.now()

            if success:
                proxy_state.success_count += 1

                # Адаптивное уменьшение задержки
                reduction_factor = self._config.success_divider

                # Для высокоприоритетных задач более агрессивное уменьшение
                if task and task.priority in [TaskPriority.CRITICAL, TaskPriority.HIGH]:
                    reduction_factor *= 1.2

                proxy_state.current_delay = max(
                    proxy_state.current_delay / reduction_factor,
                    self._config.base_delay
                )
                proxy_state.base_delay = max( # Добавлено
                    proxy_state.base_delay / reduction_factor,
                    self._config.base_delay
                )
            else:
                proxy_state.error_count += 1

                # Адаптивное увеличение задержки
                increase_factor = self._config.error_multiplier

                # Для критических задач менее агрессивное увеличение
                if task and task.priority == TaskPriority.CRITICAL:
                    increase_factor = min(increase_factor, 1.2)

                # Для фоновых задач более агрессивное увеличение
                elif task and task.priority == TaskPriority.BACKGROUND:
                    increase_factor *= 1.5

                proxy_state.current_delay = min(
                    proxy_state.current_delay * increase_factor,
                    self._config.max_delay
                )
                proxy_state.base_delay = min( # Добавлено
                    proxy_state.base_delay * increase_factor,
                    self._config.max_delay
                )

                # Дополнительная задержка для определенных типов ошибок
                if error_type:
                    if "rate_limit" in error_type.lower():
                        proxy_state.current_delay = min(
                            proxy_state.current_delay * 2.0,
                            self._config.max_delay
                        )
                        proxy_state.base_delay = min( # Добавлено
                            proxy_state.base_delay * 2.0,
                            self._config.max_delay
                        )
                    elif "timeout" in error_type.lower():
                        proxy_state.current_delay = min(
                            proxy_state.current_delay * 1.3,
                            self._config.max_delay
                        )
                        proxy_state.base_delay = min( # Добавлено
                            proxy_state.base_delay * 1.3,
                            self._config.max_delay
                        )

            logger.debug(
                f"Updated delay for proxy {proxy_id}: current_delay={proxy_state.current_delay}s, base_delay={proxy_state.base_delay}s " # Изменено
                f"(success: {success}, task_priority: {task.priority.name if task else 'None'})"
            )
            
    async def get_delay_per_profile(self, proxy_id: str) -> float:
        """Получить задержку на профиль для конкретного прокси"""
        async with self._lock:
            proxy_state = self._proxy_delays.get(proxy_id)
            if not proxy_state:
                return self._config.base_delay
            
            active_profiles_count = len(proxy_state.active_profiles)
            return proxy_state.current_delay / active_profiles_count if active_profiles_count > 0 else proxy_state.current_delay

    
    async def get_optimal_delay_for_priority(self, proxy_id: str, 
                                       priority: TaskPriority) -> float:
        """Получить оптимальную задержку для задач определенного приоритета"""
        async with self._lock:
            proxy_state = self._proxy_delays.get(proxy_id)
            if not proxy_state:
                return self._config.base_delay
            
            # Базовая задержка прокси
            base_proxy_delay = proxy_state.current_delay
            
            # Количество активных профилей на прокси
            active_profiles_count = len(proxy_state.active_profiles)
            
            # Задержка на профиль
            delay_per_profile = base_proxy_delay / active_profiles_count if active_profiles_count > 0 else base_proxy_delay
            
            # Множитель приоритета
            priority_multiplier = self._config.priority_multipliers.get(priority, 1.0)
            
            return delay_per_profile * priority_multiplier
    
    async def set_priority_multiplier(self, priority: TaskPriority, multiplier: float):
        """Установить множитель для приоритета"""
        async with self._lock:
            self._config.priority_multipliers[priority] = multiplier
    
    async def get_priority_stats(self, proxy_id: str) -> Dict[TaskPriority, Dict[str, Any]]:
        """Получить статистику по приоритетам для прокси"""
        async with self._lock:
            stats = {}
            
            for priority in TaskPriority:
                multiplier = self._config.priority_multipliers.get(priority, 1.0)
                last_execution = None
                
                if proxy_id in self._last_priority_execution:
                    last_execution = self._last_priority_execution[proxy_id].get(priority)
                
                stats[priority] = {
                    'multiplier': multiplier,
                    'last_execution': last_execution.isoformat() if last_execution else None,
                    'optimal_delay': await self.get_optimal_delay_for_priority(proxy_id, priority)
                }
            
            return stats
    
    async def remove_profile_from_proxy(self, profile_id: str, proxy_id: str):
        """Удалить профиль из активных для прокси"""
        async with self._lock:
            proxy_state = self._proxy_delays.get(proxy_id)
            if proxy_state and profile_id in proxy_state.active_profiles:
                proxy_state.active_profiles.remove(profile_id)
    
    async def get_proxy_stats(self, proxy_id: str) -> Optional[Dict[str, Any]]:
        """Получить полную статистику прокси"""
        async with self._lock:
            proxy_state = self._proxy_delays.get(proxy_id)
            if not proxy_state:
                return None

            priority_stats = await self.get_priority_stats(proxy_id)

            # Вычислить задержку на профиль
            active_profiles_count = len(proxy_state.active_profiles)
            delay_per_profile = proxy_state.base_delay / active_profiles_count if active_profiles_count > 0 else proxy_state.base_delay # Изменено

            return {
                'proxy_id': proxy_state.proxy_id,
                'current_delay': proxy_state.current_delay,
                'base_delay': proxy_state.base_delay,
                'delay_per_profile': delay_per_profile,
                'active_profiles_count': active_profiles_count,
                'success_count': proxy_state.success_count,
                'error_count': proxy_state.error_count,
                'active_profiles': proxy_state.active_profiles.copy(),
                'last_request_time': proxy_state.last_request_time.isoformat() if proxy_state.last_request_time else None,
                'priority_stats': priority_stats
            }
    
    async def optimize_delays_for_proxy(self, proxy_id: str):
        """Оптимизировать задержки для прокси на основе статистики"""
        async with self._lock:
            proxy_state = self._proxy_delays.get(proxy_id)
            if not proxy_state:
                return
            
            # Логика оптимизации на основе статистики
            success_rate = proxy_state.success_count / (proxy_state.success_count + proxy_state.error_count) if (proxy_state.success_count + proxy_state.error_count) > 0 else 0.5
            
            if success_rate > 0.9:
                # Высокий успех - можно уменьшить задержку
                proxy_state.current_delay = max(
                    proxy_state.current_delay * 0.9,
                    self._config.base_delay
                )
            elif success_rate < 0.7:
                # Низкий успех - увеличить задержку
                proxy_state.current_delay = min(
                    proxy_state.current_delay * 1.1,
                    self._config.max_delay
                )