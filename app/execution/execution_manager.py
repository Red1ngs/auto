# app/execution/execution_manager.py
import asyncio
import logging
from typing import Dict, List, Optional, Any
from multiprocessing import Process

from app.models.execution_models import (
    ExecutionMode, ProfileTask, TaskPriority
)
from app.execution.delay_manager import DelayManager
from app.execution.profile_executor import ProfileExecutor
from app.execution.queue_manager import QueueManager

from app.profiles.profile_manager import Profile

logger = logging.getLogger(__name__)

class ExecutionManager:
    """Менеджер виконання профілів з підтримкою пріоритетів"""
    
    def __init__(self, mode: ExecutionMode = ExecutionMode.ASYNC_TASKS):
        self.mode = mode
        self.delay_manager = DelayManager()
        self.queue_manager = QueueManager()
        self.profile_executor = ProfileExecutor(self.delay_manager, self.queue_manager)
        
        self._processes: Dict[str, Process] = {}
        
        # Обмеження
        self._max_profiles_per_proxy = 5
        self._proxy_profiles: Dict[str, List[str]] = {}
        
        # Статистика
        self._global_stats = {
            'total_profiles': 0,
            'active_profiles': 0,
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0
        }
        
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Налаштувати базові обробники дій"""
        
        async def http_request_handler(profile: Profile, params, proxy_id: str = None, task: ProfileTask = None):
            """Обробник HTTP-запитів"""
            from datetime import datetime
            now = datetime.now()
            print(now.strftime("%H:%M:%S"))
            client = profile.http.get_client(use_account=False)
            await client.init_session()
            method = params.get('method', 'GET')
            url = params['url']

            # Get delay for profile with consideration of proxy and priority
            if task and proxy_id:
                delay = await self.delay_manager.get_delay_for_profile(
                    profile.profile_id, proxy_id, task
                )
                await asyncio.sleep(delay)

            try:
                if method == 'GET':
                    response = await client.get(url)
                elif method == 'POST':
                    response = await client.post(url, json=params.get('json'))
                elif method == 'PUT':
                    response = await client.put(url, json=params.get('json'))
                elif method == 'DELETE':
                    response = await client.delete(url)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Ensure the response is properly read before returning
                try:
                    if response:
                        await response.text() # Ensure full read
                    return {"success": True, "result": response} # Consistent return type
                except Exception as e:
                    logger.error(f"Error reading response: {e}")
                    return {"success": False, "error": str(e)}

            except Exception as e:
                logger.exception(f"HTTP request failed: {e}")
                return {"success": False, "error": str(e)}  # Indicate failure and error
        
        async def data_processing_handler(profile, params, proxy_id: str = None, task: ProfileTask = None):
            """Обробник обробки даних"""
            processing_type = params.get('type', 'default')
            data = params.get('data')
            
            if processing_type == 'json_parse':
                import json
                return json.loads(data), None
            elif processing_type == 'csv_parse':
                import csv
                import io
                reader = csv.DictReader(io.StringIO(data))
                return list(reader), None
            else:
                # Загальна обробка
                return {'processed': True, 'data': data}, None
        
        async def save_data_handler(profile, params, proxy_id: str = None, task: ProfileTask = None):
            """Обробник збереження даних"""
            data = params.get('data')
            filename = params.get('filename')
            format_type = params.get('format', 'json')
            
            if format_type == 'json':
                import json
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
            elif format_type == 'csv':
                import csv
                with open(filename, 'w', newline='') as f:
                    if data and isinstance(data, list):
                        writer = csv.DictWriter(f, fieldnames=data[0].keys())
                        writer.writeheader()
                        writer.writerows(data)
            
            return {'saved': True, 'filename': filename}, None
        
        async def delay_handler(profile, params, proxy_id: str = None, task: ProfileTask = None):
            """Обробник затримки"""
            delay = params.get('delay', 1.0)
            await asyncio.sleep(delay)
            return {'delayed': True, 'delay': delay}, None
        
        self.profile_executor.register_action_handler('http_request', http_request_handler)
        self.profile_executor.register_action_handler('process_data', data_processing_handler)
        self.profile_executor.register_action_handler('save_data', save_data_handler)
        self.profile_executor.register_action_handler('delay', delay_handler)
    
    async def start_profile_execution(self, profile_id: str, proxy_id: str) -> bool:
        """Запустити виконання профілю"""
        
        # Перевірити обмеження на кількість профілів на проксі
        if not self._can_start_profile_on_proxy(proxy_id):
            logger.warning(f"Cannot start profile {profile_id}: proxy {proxy_id} limit reached")
            return False
        
        # Створити чергу задач з пріоритетами для профілю
        task_queue = await self.queue_manager.create_profile_queue(profile_id)
        
        # Додати профіль до проксі
        if proxy_id not in self._proxy_profiles:
            self._proxy_profiles[proxy_id] = []
        self._proxy_profiles[proxy_id].append(profile_id)
        
        # Оновити статистику
        self._global_stats['total_profiles'] += 1
        self._global_stats['active_profiles'] += 1
        
        if self.mode == ExecutionMode.ASYNC_TASKS:
            # Запустити як асинхронну задачу
            success = await self.profile_executor.start_profile(
                profile_id, proxy_id, task_queue
            )
            
            if success:
                logger.info(f"Started profile {profile_id} on proxy {proxy_id}")
            else:
                # Відкатити зміни при невдачі
                self._proxy_profiles[proxy_id].remove(profile_id)
                self._global_stats['active_profiles'] -= 1
                await self.queue_manager.remove_profile_queue(profile_id)
            
            return success
        else:
            # Запустити як окремий процес
            return self._start_profile_process(profile_id, proxy_id)
    
    async def stop_profile_execution(self, profile_id: str) -> bool:
        """Зупинити виконання профілю"""
        
        # Видалити з проксі
        for proxy_id, profiles in self._proxy_profiles.items():
            if profile_id in profiles:
                profiles.remove(profile_id)
                break
        
        # Очистити чергу
        await self.queue_manager.remove_profile_queue(profile_id)

        
        # Оновити статистику
        if self._global_stats['active_profiles'] > 0:
            self._global_stats['active_profiles'] -= 1
        
        if self.mode == ExecutionMode.ASYNC_TASKS:
            success = await self.profile_executor.stop_profile(profile_id)
            if success:
                logger.info(f"Stopped profile {profile_id}")
            return success
        else:
            return self._stop_profile_process(profile_id)
    
    async def pause_profile_execution(self, profile_id: str) -> bool:
        """Призупинити виконання профілю"""
        return await self.profile_executor.pause_profile(profile_id)
    
    async def resume_profile_execution(self, profile_id: str) -> bool:
        """Відновити виконання профілю"""
        return await self.profile_executor.resume_profile(profile_id)
    
    async def add_task_to_profile(self, profile_id: str, task: ProfileTask):
        """Додати задачу до профілю"""
        await self.queue_manager.add_task_to_profile(profile_id, task)
        
        # Оновити статистику
        self._global_stats['total_tasks'] += 1
        
        # Оновити кількість очікуючих задач у стані виконання
        state = self.profile_executor.get_execution_state(profile_id)
        if state:
            state.pending_tasks += 1
        
        logger.debug(f"Added task {task.task_id} with priority {task.priority.name} to profile {profile_id}")
    
    async def add_tasks_to_profile(self, profile_id: str, tasks: List[ProfileTask]):
        """Додати кілька задач до профілю"""
        for task in tasks:
            await self.add_task_to_profile(profile_id, task)
    
    async def cancel_task(self, profile_id: str, task_id: str) -> bool:
        """Скасувати задачу"""
        return await self.queue_manager.cancel_task(profile_id, task_id)
    
    async def get_task_result(self, profile_id: str, task_id: str, timeout: float = 30.0):
        return await self.queue_manager.get_task_result(profile_id, task_id, timeout)
    
    async def get_profile_execution_state(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Отримати стан виконання профілю"""
        return await self.profile_executor.get_profile_stats(profile_id)
    
    async def get_profile_queue_stats(self, profile_id: str) -> Dict[str, Any]:
        """Отримати статистику черги профілю"""
        return await self.queue_manager.get_profile_queue_stats(profile_id)
    
    async def get_proxy_delay_stats(self, proxy_id: str) -> Optional[Dict[str, Any]]:
        """Отримати статистику затримок проксі"""
        return await self.delay_manager.get_proxy_stats(proxy_id)
    
    async def set_proxy_base_delay(self, proxy_id: str, base_delay: float):
        """Установить базовую задержку для прокси"""
        await self.delay_manager.set_proxy_base_delay(proxy_id, base_delay)
        
    async def optimize_proxy_delays(self, proxy_id: str):
        """Оптимізувати затримки для проксі"""
        await self.delay_manager.optimize_delays_for_proxy(proxy_id)
    
    async def set_priority_multiplier(self, priority: TaskPriority, multiplier: float):
        """Встановити множник для пріоритету"""
        await self.delay_manager.set_priority_multiplier(priority, multiplier)
    
    def _can_start_profile_on_proxy(self, proxy_id: str) -> bool:
        """Перевірити, чи можна запустити профіль на проксі"""
        current_count = len(self._proxy_profiles.get(proxy_id, []))
        return current_count < self._max_profiles_per_proxy
    
    def get_proxy_usage_stats(self) -> Dict[str, Any]:
        """Отримати статистику використання проксі"""
        stats = {}
        for proxy_id, profiles in self._proxy_profiles.items():
            stats[proxy_id] = {
                'active_profiles': len(profiles),
                'max_profiles': self._max_profiles_per_proxy,
                'profiles': profiles,
                'usage_percentage': (len(profiles) / self._max_profiles_per_proxy) * 100
            }
        return stats
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """Отримати глобальну статистику"""
        queue_stats = await self.queue_manager.get_global_stats()
        
        # Додати статистику виконання
        execution_states = self.profile_executor.get_all_execution_states()
        profile_stats = {}
        
        for profile_id, state in execution_states.items():
            profile_stats[profile_id] = await self.profile_executor.get_profile_stats(profile_id)
        
        return {
            'global_stats': self._global_stats,
            'queue_stats': queue_stats,
            'profile_stats': profile_stats,
            'proxy_usage': self.get_proxy_usage_stats()
        }
    
    def set_max_profiles_per_proxy(self, max_profiles: int):
        """Встановити максимальну кількість профілів на проксі"""
        self._max_profiles_per_proxy = max_profiles
        logger.info(f"Set max profiles per proxy to {max_profiles}")
        
    async def get_priority_stats(self, proxy_id: str) -> Dict[str, Any]:
        """Отримати статистику пріоритетів для проксі"""
        return await self.delay_manager.get_priority_stats(proxy_id)