# app/execution/state_manager.py
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from app.models.execution_models import (
    ProfileExecutionState, ProxyDelayState, DelayConfig, 
    TaskPriority, ProfileTask, ProfileStatus
)

logger = logging.getLogger(__name__)

class StateManager:
    """Менеджер збереження стану системи виконання з підтримкою пріоритетів"""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self._state: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._auto_save_interval = 30  # секунд
        self._auto_save_task: Optional[asyncio.Task] = None
        
        # Структура стану для системи виконання
        self._default_state = {
            'profiles': {},
            'proxies': {},
            'tasks': {},
            'global_stats': {
                'total_profiles': 0,
                'active_profiles': 0,
                'total_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0
            },
            'delay_config': {},
            'priority_multipliers': {
                TaskPriority.CRITICAL.name: 0.1,
                TaskPriority.HIGH.name: 0.5,
                TaskPriority.NORMAL.name: 1.0,
                TaskPriority.LOW.name: 1.5,
                TaskPriority.BACKGROUND.name: 2.0
            },
            'proxy_usage': {},
            'last_updated': None
        }
    
    async def initialize(self):
        """Ініціалізувати менеджер стану"""
        await self._load_state()
        self._start_auto_save()
    
    async def _load_state(self):
        """Завантажити стан з файлу"""
        async with self._lock:
            if self.state_file.exists():
                try:
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        loaded_state = json.load(f)
                    
                    # Злити з базовим станом
                    self._state = {**self._default_state, **loaded_state}
                    
                    logger.info(f"Loaded state from {self.state_file}")
                except Exception as e:
                    logger.error(f"Failed to load state: {e}")
                    self._state = self._default_state.copy()
            else:
                self._state = self._default_state.copy()
    
    async def save_state(self):
        """Зберегти стан у файл"""
        async with self._lock:
            try:
                # Створити директорію, якщо не існує
                self.state_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Оновити час останнього збереження
                self._state['last_updated'] = datetime.now().isoformat()
                
                # Зберегти стан
                with open(self.state_file, 'w', encoding='utf-8') as f:
                    json.dump(self._state, f, ensure_ascii=False, indent=2, default=str)
                
                logger.debug(f"State saved to {self.state_file}")
            except Exception as e:
                logger.error(f"Failed to save state: {e}")
    
    # Методи для роботи з профілями
    async def save_profile_state(self, profile_id: str, state: ProfileExecutionState):
        """Зберегти стан профілю"""
        async with self._lock:
            self._state['profiles'][profile_id] = {
                'profile_id': state.profile_id,
                'status': state.status.value,
                'started_at': state.started_at.isoformat(),
                'last_activity': state.last_activity.isoformat(),
                'current_action': state.current_action,
                'success_count': state.success_count,
                'error_count': state.error_count,
                'pending_tasks': state.pending_tasks,
                'current_task_priority': state.current_task_priority.name if state.current_task_priority else None,
                'completed_tasks': list(state.completed_tasks)
            }
    
    async def load_profile_state(self, profile_id: str) -> Optional[ProfileExecutionState]:
        """Завантажити стан профілю"""
        async with self._lock:
            profile_data = self._state['profiles'].get(profile_id)
            if not profile_data:
                return None
            
            try:
                return ProfileExecutionState(
                    profile_id=profile_data['profile_id'],
                    status=ProfileStatus(profile_data['status']),
                    started_at=datetime.fromisoformat(profile_data['started_at']),
                    last_activity=datetime.fromisoformat(profile_data['last_activity']),
                    current_action=profile_data.get('current_action'),
                    success_count=profile_data.get('success_count', 0),
                    error_count=profile_data.get('error_count', 0),
                    pending_tasks=profile_data.get('pending_tasks', 0),
                    current_task_priority=TaskPriority[profile_data['current_task_priority']] if profile_data.get('current_task_priority') else None,
                    completed_tasks=set(profile_data.get('completed_tasks', []))
                )
            except Exception as e:
                logger.error(f"Failed to load profile state for {profile_id}: {e}")
                return None
    
    async def remove_profile_state(self, profile_id: str):
        """Видалити стан профілю"""
        async with self._lock:
            if profile_id in self._state['profiles']:
                del self._state['profiles'][profile_id]
    
    # Методи для роботи з проксі
    async def save_proxy_state(self, proxy_id: str, state: ProxyDelayState):
        """Зберегти стан проксі"""
        async with self._lock:
            self._state['proxies'][proxy_id] = {
                'proxy_id': state.proxy_id,
                'current_delay': state.current_delay,
                'base_delay': state.base_delay,  # Добавлено
                'last_request_time': state.last_request_time.isoformat() if state.last_request_time else None,
                'success_count': state.success_count,
                'error_count': state.error_count,
                'active_profiles': state.active_profiles.copy()
            }
    
    async def load_proxy_state(self, proxy_id: str) -> Optional[ProxyDelayState]:
        """Завантажити стан проксі"""
        async with self._lock:
            proxy_data = self._state['proxies'].get(proxy_id)
            if not proxy_data:
                return None

            try:
                return ProxyDelayState(
                    proxy_id=proxy_data['proxy_id'],
                    current_delay=proxy_data.get('current_delay', 2.0),
                    base_delay=proxy_data.get('base_delay', 2.0),
                    last_request_time=datetime.fromisoformat(proxy_data['last_request_time']) if proxy_data.get('last_request_time') else None,
                    success_count=proxy_data.get('success_count', 0),
                    error_count=proxy_data.get('error_count', 0),
                    active_profiles=proxy_data.get('active_profiles', [])
                )
            except Exception as e:
                logger.error(f"Failed to load proxy state for {proxy_id}: {e}")
                return None
    
    async def remove_proxy_state(self, proxy_id: str):
        """Видалити стан проксі"""
        async with self._lock:
            if proxy_id in self._state['proxies']:
                del self._state['proxies'][proxy_id]
    
    # Методи для роботи з задачами
    async def save_task(self, task: ProfileTask):
        """Зберегти задачу"""
        async with self._lock:
            self._state['tasks'][task.task_id] = {
                'task_id': task.task_id,
                'profile_id': task.profile_id,
                'action': task.action,
                'params': task.params,
                'priority': task.priority.name,
                'created_at': task.created_at.isoformat(),
                'scheduled_at': task.scheduled_at.isoformat() if task.scheduled_at else None,
                'max_retries': task.max_retries,
                'retry_count': task.retry_count,
                'dependencies': task.dependencies
            }
    
    async def load_task(self, task_id: str) -> Optional[ProfileTask]:
        """Завантажити задачу"""
        async with self._lock:
            task_data = self._state['tasks'].get(task_id)
            if not task_data:
                return None
            
            try:
                return ProfileTask(
                    task_id=task_data['task_id'],
                    profile_id=task_data['profile_id'],
                    action=task_data['action'],
                    params=task_data['params'],
                    priority=TaskPriority[task_data['priority']],
                    created_at=datetime.fromisoformat(task_data['created_at']),
                    scheduled_at=datetime.fromisoformat(task_data['scheduled_at']) if task_data.get('scheduled_at') else None,
                    max_retries=task_data.get('max_retries', 3),
                    retry_count=task_data.get('retry_count', 0),
                    dependencies=task_data.get('dependencies', [])
                )
            except Exception as e:
                logger.error(f"Failed to load task {task_id}: {e}")
                return None
    
    async def remove_task(self, task_id: str):
        """Видалити задачу"""
        async with self._lock:
            if task_id in self._state['tasks']:
                del self._state['tasks'][task_id]
    
    async def get_pending_tasks_for_profile(self, profile_id: str) -> List[ProfileTask]:
        """Отримати незавершені задачі для профілю"""
        async with self._lock:
            tasks = []
            for task_data in self._state['tasks'].values():
                if task_data.get('profile_id') == profile_id:
                    task = await self.load_task(task_data['task_id'])
                    if task:
                        tasks.append(task)
            return tasks
    
    # Методи для роботи з глобальною статистикою
    async def update_global_stats(self, stats: Dict[str, Any]):
        """Оновити глобальну статистику"""
        async with self._lock:
            self._state['global_stats'].update(stats)
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """Отримати глобальну статистику"""
        async with self._lock:
            return self._state['global_stats'].copy()
    
    async def increment_stat(self, stat_name: str, value: int = 1):
        """Збільшити значення статистики"""
        async with self._lock:
            if stat_name in self._state['global_stats']:
                self._state['global_stats'][stat_name] += value
    
    # Методи для роботи з конфігурацією
    async def save_delay_config(self, config: DelayConfig):
        """Зберегти конфігурацію затримок"""
        async with self._lock:
            self._state['delay_config'] = {
                'base_delay': config.base_delay,
                'max_delay': config.max_delay,
                'success_divider': config.success_divider,
                'error_multiplier': config.error_multiplier,
                'proxy_shared_multiplier': config.proxy_shared_multiplier,
                'priority_multipliers': {
                    priority.name: multiplier 
                    for priority, multiplier in config.priority_multipliers.items()
                }
            }
    
    async def load_delay_config(self) -> DelayConfig:
        """Завантажити конфігурацію затримок"""
        async with self._lock:
            config_data = self._state.get('delay_config', {})
            
            # Створити базову конфігурацію
            config = DelayConfig()
            
            # Оновити значення з збережених даних
            if config_data:
                config.base_delay = config_data.get('base_delay', config.base_delay)
                config.max_delay = config_data.get('max_delay', config.max_delay)
                config.success_divider = config_data.get('success_divider', config.success_divider)
                config.error_multiplier = config_data.get('error_multiplier', config.error_multiplier)
                config.proxy_shared_multiplier = config_data.get('proxy_shared_multiplier', config.proxy_shared_multiplier)
                
                # Завантажити множники пріоритетів
                priority_multipliers = config_data.get('priority_multipliers', {})
                for priority_name, multiplier in priority_multipliers.items():
                    try:
                        priority = TaskPriority[priority_name]
                        config.priority_multipliers[priority] = multiplier
                    except KeyError:
                        logger.warning(f"Unknown priority: {priority_name}")
            
            return config
    
    async def set_priority_multiplier(self, priority: TaskPriority, multiplier: float):
        """Встановити множник для пріоритету"""
        async with self._lock:
            self._state['priority_multipliers'][priority.name] = multiplier
    
    async def get_priority_multiplier(self, priority: TaskPriority) -> float:
        """Отримати множник для пріоритету"""
        async with self._lock:
            return self._state['priority_multipliers'].get(priority.name, 1.0)
    
    # Методи для роботи з використанням проксі
    async def update_proxy_usage(self, proxy_id: str, usage_data: Dict[str, Any]):
        """Оновити інформацію про використання проксі"""
        async with self._lock:
            if 'proxy_usage' not in self._state:
                self._state['proxy_usage'] = {}
            self._state['proxy_usage'][proxy_id] = usage_data
    
    async def get_proxy_usage(self, proxy_id: str) -> Dict[str, Any]:
        """Отримати інформацію про використання проксі"""
        async with self._lock:
            return self._state.get('proxy_usage', {}).get(proxy_id, {})
    
    async def get_all_proxy_usage(self) -> Dict[str, Dict[str, Any]]:
        """Отримати інформацію про використання всіх проксі"""
        async with self._lock:
            return self._state.get('proxy_usage', {}).copy()
    
    # Загальні методи
    async def update_state(self, key: str, value: Any):
        """Оновити значення у стані"""
        async with self._lock:
            self._state[key] = value
            self._state['last_updated'] = datetime.now().isoformat()
    
    async def get_state(self, key: str, default: Any = None) -> Any:
        """Отримати значення зі стану"""
        async with self._lock:
            return self._state.get(key, default)
    
    async def remove_state(self, key: str):
        """Видалити ключ зі стану"""
        async with self._lock:
            if key in self._state:
                del self._state[key]
    
    async def get_full_state(self) -> Dict[str, Any]:
        """Отримати повний стан системи"""
        async with self._lock:
            return self._state.copy()
    
    async def restore_execution_state(self) -> Dict[str, Any]:
        """Відновити стан виконання після перезапуску"""
        async with self._lock:
            restoration_data = {
                'profiles': {},
                'proxies': {},
                'pending_tasks': {},
                'global_stats': self._state.get('global_stats', {}),
                'delay_config': await self.load_delay_config()
            }
            
            # Завантажити стани профілів
            for profile_id in self._state.get('profiles', {}):
                profile_state = await self.load_profile_state(profile_id)
                if profile_state:
                    restoration_data['profiles'][profile_id] = profile_state
            
            # Завантажити стани проксі
            for proxy_id in self._state.get('proxies', {}):
                proxy_state = await self.load_proxy_state(proxy_id)
                if proxy_state:
                    restoration_data['proxies'][proxy_id] = proxy_state
            
            # Завантажити незавершені задачі
            for profile_id in self._state.get('profiles', {}):
                tasks = await self.get_pending_tasks_for_profile(profile_id)
                if tasks:
                    restoration_data['pending_tasks'][profile_id] = tasks
            
            return restoration_data
    
    def _start_auto_save(self):
        """Запустити автоматичне збереження"""
        if self._auto_save_task:
            self._auto_save_task.cancel()
        self._auto_save_task = asyncio.create_task(self._auto_save_loop())
    
    async def _auto_save_loop(self):
        """Цикл автоматичного збереження"""
        while True:
            try:
                await asyncio.sleep(self._auto_save_interval)
                await self.save_state()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-save error: {e}")
    
    def set_auto_save_interval(self, seconds: int):
        """Встановити інтервал автоматичного збереження"""
        self._auto_save_interval = seconds
        if self._auto_save_task:
            self._auto_save_task.cancel()
            self._start_auto_save()
    
    async def cleanup_old_data(self, days_old: int = 30):
        """Очистити старі дані"""
        async with self._lock:
            cutoff_date = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            
            # Очистити старі задачі
            tasks_to_remove = []
            for task_id, task_data in self._state.get('tasks', {}).items():
                try:
                    created_at = datetime.fromisoformat(task_data['created_at'])
                    if created_at.timestamp() < cutoff_date:
                        tasks_to_remove.append(task_id)
                except:  # noqa: E722
                    # Видалити некоректні записи
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self._state['tasks'][task_id]
            
            logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")
    
    async def shutdown(self):
        """Завершити роботу менеджера"""
        if self._auto_save_task:
            self._auto_save_task.cancel()
            try:
                await self._auto_save_task
            except asyncio.CancelledError:
                pass
        
        await self.save_state()
        logger.info("StateManager shut down")