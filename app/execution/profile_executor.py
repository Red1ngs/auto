# app/execution/profile_executor.py
import asyncio
import logging
from typing import Dict, Optional, Callable, Any
from datetime import datetime

from app.models.execution_models import (
    ProfileExecutionState, ProfileStatus, ProfileTask
)
from app.execution.delay_manager import DelayManager
from app.execution.queue_manager import PriorityTaskQueue, QueueManager
from app.profiles.profile_manager import Profile, profile_manager

logger = logging.getLogger(__name__)

class ProfileExecutor:
    """Виконавець профілів з підтримкою пріоритетів"""
    
    def __init__(self, delay_manager: DelayManager, queue_manager: QueueManager):
        self.delay_manager = delay_manager
        self.queue_manager = queue_manager
        self._execution_states: Dict[str, ProfileExecutionState] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._action_handlers: Dict[str, Callable] = {}
        self._lock = asyncio.Lock()
    
    def register_action_handler(self, action: str, handler: Callable):
        """Зареєструвати обробник дії"""
        self._action_handlers[action] = handler
    
    async def start_profile(self, profile_id: str, proxy_id: str, 
                          task_queue: PriorityTaskQueue) -> bool:
        """Запустити виконання профілю"""
        async with self._lock:
            if profile_id in self._running_tasks:
                logger.warning(f"Profile {profile_id} is already running")
                return False
            
            # Ініціалізувати стан виконання
            self._execution_states[profile_id] = ProfileExecutionState(
                profile_id=profile_id,
                status=ProfileStatus.RUNNING,
                started_at=datetime.now(),
                last_activity=datetime.now(),
                completed_tasks=set()
            )
            
            # Створити задачу виконання
            task = asyncio.create_task(
                self._execute_profile(profile_id, proxy_id, task_queue)
            )
            self._running_tasks[profile_id] = task
            
            logger.info(f"Started profile execution: {profile_id}")
            return True
    
    async def stop_profile(self, profile_id: str) -> bool:
        """Зупинити виконання профілю"""
        async with self._lock:
            if profile_id not in self._running_tasks:
                logger.warning(f"Profile {profile_id} is not running")
                return False
            
            task = self._running_tasks[profile_id]
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            del self._running_tasks[profile_id]
            
            # Оновити стан
            if profile_id in self._execution_states:
                self._execution_states[profile_id].status = ProfileStatus.STOPPED
            
            logger.info(f"Stopped profile execution: {profile_id}")
            return True
    
    async def pause_profile(self, profile_id: str) -> bool:
        """Призупинити виконання профілю"""
        async with self._lock:
            if profile_id in self._execution_states:
                self._execution_states[profile_id].status = ProfileStatus.PAUSED
                logger.info(f"Paused profile execution: {profile_id}")
                return True
            return False
    
    async def resume_profile(self, profile_id: str) -> bool:
        """Відновити виконання профілю"""
        async with self._lock:
            if profile_id in self._execution_states:
                self._execution_states[profile_id].status = ProfileStatus.RUNNING
                logger.info(f"Resumed profile execution: {profile_id}")
                return True
            return False
    
    async def _execute_profile(self, profile_id: str, proxy_id: str, 
                             task_queue: PriorityTaskQueue):
        """Основний цикл виконання профілю з підтримкою пріоритетів"""
        try:
            profile = profile_manager.get_profile(profile_id)
            
            while True:
                # Перевірити стан
                state = self._execution_states.get(profile_id)
                if not state or state.status == ProfileStatus.STOPPED:
                    break
                
                if state.status == ProfileStatus.PAUSED:
                    await asyncio.sleep(1)
                    continue
                
                try:
                    # Отримати задачу з черги з пріоритетом
                    task = await task_queue.get(timeout=1.0)
                    if not task:
                        continue
                    
                    # Перевірити, чи можна виконати задачу
                    if not task.can_execute(state.completed_tasks):
                        # Повернути задачу в чергу
                        await task_queue.put(task)
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Оновити поточний пріоритет
                    state.current_task_priority = task.priority
                    
                    # Виконати дію
                    await self._execute_task(profile, task, proxy_id)

                    # Оновити стан
                    state.last_activity = datetime.now()
                    state.success_count += 1
                    state.current_action = None
                    state.current_task_priority = None
                    state.completed_tasks.add(task.task_id)
                    
                    # Зменшити кількість очікуючих задач
                    if state.pending_tasks > 0:
                        state.pending_tasks -= 1
                    
                    logger.debug(f"Completed task {task.task_id} with priority {task.priority.name}")
                    
                except asyncio.TimeoutError:
                    # Немає задач у черзі
                    continue
                except Exception as e:
                    logger.error(f"Error executing task for profile {profile_id}: {e}")
                    state.error_count += 1
                    
                    # Записати помилку з інформацією про задачу
                    current_task = getattr(state, '_current_task', None)
                    await self.delay_manager.record_request_result(
                        profile_id, proxy_id, False, current_task, str(e)
                    )
                    
                    # Повторити задачу, якщо є спроби
                    if hasattr(state, '_current_task') and state._current_task:
                        task = state._current_task
                        if task.retry_count < task.max_retries:
                            task.retry_count += 1
                            await task_queue.put(task)
                            logger.info(f"Retrying task {task.task_id}, attempt {task.retry_count}")
                        else:
                            logger.error(f"Task {task.task_id} failed after {task.max_retries} attempts")
                    
        except asyncio.CancelledError:
            logger.info(f"Profile execution cancelled: {profile_id}")
        except Exception as e:
            logger.error(f"Profile execution error: {profile_id}: {e}")
            self._execution_states[profile_id].status = ProfileStatus.ERROR
        finally:
            # Очистити ресурси
            await self.delay_manager.remove_profile_from_proxy(profile_id, proxy_id)
            
            try:
                await profile.http.close()
            except Exception as e:
                logger.error(f"Error closing HTTP client for profile {profile_id}: {e}")

    
    async def _execute_task(self, profile: Profile, task: ProfileTask, proxy_id: str):
        """Виконати конкретну задачу"""
        handler = self._action_handlers.get(task.action)
        if not handler:
            raise ValueError(f"Unknown action: {task.action}")

        state = self._execution_states[task.profile_id]
        state.current_action = task.action
        state._current_task = task

        try:
            result = await handler(profile, task.params)

            await self.delay_manager.record_request_result(
                task.profile_id, proxy_id, True, task
            )

            await self.queue_manager.set_task_result(task.profile_id, task.task_id, result)

            return result

        except Exception as e:
            await self.delay_manager.record_request_result(
                task.profile_id, proxy_id, False, task, str(e)
            )
            raise

        finally:
            if hasattr(state, '_current_task'):
                delattr(state, '_current_task')

    
    def get_execution_state(self, profile_id: str) -> Optional[ProfileExecutionState]:
        """Отримати стан виконання профілю"""
        return self._execution_states.get(profile_id)
    
    def get_all_execution_states(self) -> Dict[str, ProfileExecutionState]:
        """Отримати всі стани виконання"""
        return self._execution_states.copy()
    
    async def get_profile_stats(self, profile_id: str) -> Dict[str, Any]:
        """Отримати статистику профілю"""
        state = self._execution_states.get(profile_id)
        if not state:
            return {}
        
        return {
            'profile_id': profile_id,
            'status': state.status.value,
            'started_at': state.started_at.isoformat(),
            'last_activity': state.last_activity.isoformat(),
            'current_action': state.current_action,
            'current_priority': state.current_task_priority.name if state.current_task_priority else None,
            'success_count': state.success_count,
            'error_count': state.error_count,
            'pending_tasks': state.pending_tasks,
            'completed_tasks_count': len(state.completed_tasks)
        }