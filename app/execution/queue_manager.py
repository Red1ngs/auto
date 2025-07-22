# app/execution/queue_manager.py
import asyncio
import heapq
from typing import Dict, Any, Optional, List

from app.models.execution_models import ProfileTask, TaskPriority

class PriorityTaskQueue:
    """Очередь задач с приоритетами"""
    
    def __init__(self):
        self._heap: List[ProfileTask] = []
        self._task_registry: Dict[str, ProfileTask] = {}
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
    
    async def put(self, task: ProfileTask):
        """Добавить задачу в очередь с приоритетом"""
        async with self._condition:
            # Зарегистрировать задачу
            self._task_registry[task.task_id] = task
            
            # Добавить в кучу с приоритетом
            heapq.heappush(self._heap, task)
            
            # Уведомить ожидающих
            self._condition.notify()
    
    async def get(self, timeout: Optional[float] = None) -> Optional[ProfileTask]:
        """Получить задачу с наивысшим приоритетом"""
        async with self._condition:
            deadline = None
            if timeout is not None:
                deadline = asyncio.get_event_loop().time() + timeout
            
            while not self._heap:
                if deadline is not None:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        return None
                    
                    try:
                        await asyncio.wait_for(self._condition.wait(), timeout=remaining)
                    except asyncio.TimeoutError:
                        return None
                else:
                    await self._condition.wait()
            
            # Найти задачу, которую можно выполнить
            available_tasks = []
            unavailable_tasks = []
            
            # Извлечь все задачи из кучи
            while self._heap:
                task = heapq.heappop(self._heap)
                if task.task_id in self._task_registry:  # Проверить, что задача не была отменена
                    if task.can_execute(set()):  # Здесь нужно передать множество выполненных задач
                        available_tasks.append(task)
                    else:
                        unavailable_tasks.append(task)
            
            # Вернуть недоступные задачи обратно в кучу
            for task in unavailable_tasks:
                heapq.heappush(self._heap, task)
            
            # Если есть доступные задачи, вернуть с наивысшим приоритетом
            if available_tasks:
                # Отсортировать по приоритету и вернуть первую
                available_tasks.sort()
                selected_task = available_tasks[0]
                
                # Вернуть остальные задачи в кучу
                for task in available_tasks[1:]:
                    heapq.heappush(self._heap, task)
                
                return selected_task
            
            return None
 
    async def remove_task(self, task_id: str) -> bool:
        """Удалить задачу из очереди"""
        async with self._condition:
            if task_id in self._task_registry:
                del self._task_registry[task_id]
                return True
            return False
    
    async def get_pending_tasks(self) -> List[ProfileTask]:
        """Получить список ожидающих задач"""
        async with self._condition:
            return [task for task in self._heap if task.task_id in self._task_registry]
    
    async def get_priority_stats(self) -> Dict[TaskPriority, int]:
        """Получить статистику по приоритетам"""
        async with self._condition:
            stats = {priority: 0 for priority in TaskPriority}
            for task in self._heap:
                if task.task_id in self._task_registry:
                    stats[task.priority] += 1
            return stats
    
    def qsize(self) -> int:
        """Получить размер очереди"""
        return len(self._task_registry)

class QueueManager:
    """Менеджер очередей для коммуникации между интерфейсом и логикой"""
    
    def __init__(self):
        self._command_queue = asyncio.Queue()
        self._result_queue = asyncio.Queue()
        self._status_queue = asyncio.Queue()
        self._subscribers: Dict[str, asyncio.Queue] = {}
        
        self._result_futures: Dict[str, Dict[str, asyncio.Future]] = {}
        
        # Очереди с приоритетами для каждого профиля
        self._profile_queues: Dict[str, PriorityTaskQueue] = {}
        
        # Глобальная очередь для срочных задач
        self._urgent_queue = PriorityTaskQueue()
        
        # Статистика
        self._task_stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'priority_stats': {priority: 0 for priority in TaskPriority}
        }
    
    
    async def create_profile_queue(self, profile_id: str) -> PriorityTaskQueue:
        """Создать очередь для профиля"""
        queue = PriorityTaskQueue()
        self._profile_queues[profile_id] = queue
        return queue
    
    async def get_profile_queue(self, profile_id: str) -> Optional[PriorityTaskQueue]:
        """Получить очередь профиля"""
        return self._profile_queues.get(profile_id)
    
    async def remove_profile_queue(self, profile_id: str):
        """Удалить очередь профиля"""
        if profile_id in self._profile_queues:
            del self._profile_queues[profile_id]
            
    def _ensure_future_registry(self, profile_id: str):
        if profile_id not in self._result_futures:
            self._result_futures[profile_id] = {}
            
    def register_task_future(self, profile_id: str, task_id: str):
        self._ensure_future_registry(profile_id)
        future = asyncio.Future()
        self._result_futures[profile_id][task_id] = future
        return future
    
    async def set_task_result(self, profile_id: str, task_id: str, result: Any):
        self._ensure_future_registry(profile_id)
        future = self._result_futures[profile_id].get(task_id)
        if future and not future.done():
            future.set_result(result)

    async def get_task_result(self, profile_id: str, task_id: str, timeout: Optional[float] = 30.0) -> Any:
        self._ensure_future_registry(profile_id)
        future = self._result_futures[profile_id].get(task_id)

        if not future:
            raise ValueError(f"Task future not found for profile {profile_id}, task {task_id}")
        
        return await asyncio.wait_for(future, timeout)
    
    async def add_task_to_profile(self, profile_id: str, task: ProfileTask):
        """Добавить задачу в очередь профиля"""
        # Обновить статистику
        self._task_stats['total_tasks'] += 1
        self._task_stats['priority_stats'][task.priority] += 1
        
        self.register_task_future(profile_id, task.task_id)

        # Если задача критическая, добавить в срочную очередь
        if task.priority == TaskPriority.CRITICAL:
            await self._urgent_queue.put(task)
        else:
            # Добавить в очередь профиля
            queue = self._profile_queues.get(profile_id)
            if queue:
                await queue.put(task)
            else:
                # Создать очередь, если её нет
                queue = await self.create_profile_queue(profile_id)
                await queue.put(task)
    
    async def get_next_task_for_profile(self, profile_id: str, 
                                       timeout: Optional[float] = None) -> Optional[ProfileTask]:
        """Получить следующую задачу для профиля"""
        # Сначала проверить срочную очередь
        urgent_task = await self._urgent_queue.get(timeout=0.1)
        if urgent_task:
            return urgent_task
        
        # Если в срочной очереди нет задач для этого профиля, проверить обычную очередь
        queue = self._profile_queues.get(profile_id)
        if queue:
            return await queue.get(timeout=timeout)
        
        return None
    
    async def cancel_task(self, profile_id: str, task_id: str) -> bool:
        cancelled = False

        if await self._urgent_queue.remove_task(task_id):
            cancelled = True

        queue = self._profile_queues.get(profile_id)
        if queue and await queue.remove_task(task_id):
            cancelled = True

        if cancelled:
            future = self._result_futures.get(profile_id, {}).get(task_id)
            if future and not future.done():
                future.cancel()

        return cancelled

    
    async def get_profile_queue_stats(self, profile_id: str) -> Dict[str, Any]:
        """Получить статистику очереди профиля"""
        queue = self._profile_queues.get(profile_id)
        if not queue:
            return {}
        
        pending_tasks = await queue.get_pending_tasks()
        priority_stats = await queue.get_priority_stats()
        
        return {
            'pending_count': len(pending_tasks),
            'priority_stats': priority_stats,
            'pending_tasks': [
                {
                    'task_id': task.task_id,
                    'action': task.action,
                    'priority': task.priority.name,
                    'created_at': task.created_at.isoformat(),
                    'scheduled_at': task.scheduled_at.isoformat() if task.scheduled_at else None
                }
                for task in pending_tasks
            ]
        }
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """Получить глобальную статистику"""
        urgent_stats = await self._urgent_queue.get_priority_stats()
        
        profile_stats = {}
        for profile_id, queue in self._profile_queues.items():
            profile_stats[profile_id] = await self.get_profile_queue_stats(profile_id)
        
        return {
            'task_stats': self._task_stats,
            'urgent_queue_stats': urgent_stats,
            'profile_stats': profile_stats,
            'active_profiles': len(self._profile_queues)
        }
    
    async def mark_task_completed(self, task: ProfileTask, success: bool):
        """Отметить задачу как выполненную"""
        if success:
            self._task_stats['completed_tasks'] += 1
        else:
            self._task_stats['failed_tasks'] += 1
    
    # Остальные методы остаются без изменений
    async def send_command(self, command: Dict[str, Any]):
        """Отправить команду в систему выполнения"""
        await self._command_queue.put(command)
    
    async def get_command(self) -> Dict[str, Any]:
        """Получить команду для обработки"""
        return await self._command_queue.get()
    
    async def send_result(self, result: Dict[str, Any]):
        """Отправить результат выполнения"""
        await self._result_queue.put(result)
    
    async def get_result(self) -> Dict[str, Any]:
        """Получить результат выполнения"""
        return await self._result_queue.get()
    
    async def send_status_update(self, status: Dict[str, Any]):
        """Отправить обновление статуса"""
        await self._status_queue.put(status)
        
        # Разослать подписчикам
        for subscriber_queue in self._subscribers.values():
            try:
                await subscriber_queue.put(status)
            except:  # noqa: E722
                pass
    
    async def get_status_update(self) -> Dict[str, Any]:
        """Получить обновление статуса"""
        return await self._status_queue.get()
    
    def subscribe_to_status(self, subscriber_id: str) -> asyncio.Queue:
        """Подписаться на обновления статуса"""
        queue = asyncio.Queue()
        self._subscribers[subscriber_id] = queue
        return queue
    
    def unsubscribe_from_status(self, subscriber_id: str):
        """Отписаться от обновлений статуса"""
        if subscriber_id in self._subscribers:
            del self._subscribers[subscriber_id]