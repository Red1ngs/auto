
# app/execution/cluster_executor.py
import asyncio
import logging
from typing import Dict, Optional, Any, Callable, List
from datetime import datetime, timedelta

from app.models.execution_models import ProfileTask, TaskPriority, ProxyClusterState
from app.profiles.profile_manager import profile_manager

logger = logging.getLogger(__name__)


class Cluster:
    """Кластер для одного прокси с общей очередью задач"""
    
    def __init__(self, proxy_id: str, base_delay: float = 1.0):
        self.proxy_id = proxy_id
        self.state = ProxyClusterState(proxy_id, [], base_delay, base_delay)
        
        # Общая очередь задач для всех профилей этого прокси
        self._task_queue = asyncio.PriorityQueue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Обработчики действий
        self._action_handlers: Dict[str, Callable] = {}
        
        # Статистика по приоритетам
        self._priority_stats = {priority: {'count': 0, 'success': 0, 'errors': 0} 
                               for priority in TaskPriority}
    
    def register_action_handler(self, action: str, handler: Callable):
        """Регистрировать обработчик действия"""
        self._action_handlers[action] = handler
    
    async def add_task(self, task: ProfileTask):
        """Добавить задачу в очередь кластера"""
        await self._task_queue.put(task)
        self._priority_stats[task.priority]['count'] += 1
        logger.debug(f"Added task {task.task_id} to proxy cluster {self.proxy_id}")
    
    async def add_profile(self, profile_id: str):
        async with self._lock:
            if profile_id not in self.state.active_profiles:
                self.state.active_profiles.append(profile_id)
                # Один раз настроить прокси для профиля
                profile = profile_manager.get_profile(profile_id)
                profile.http.put_proxy(self.proxy_id)
                logger.info(f"Added profile {profile_id} to proxy cluster {self.proxy_id} and set proxy")

    
    async def remove_profile(self, profile_id: str):
        """Удалить профиль из кластера"""
        async with self._lock:
            if profile_id in self.state.active_profiles:
                self.state.active_profiles.remove(profile_id)
                logger.info(f"Removed profile {profile_id} from proxy cluster {self.proxy_id}")
    
    async def start(self):
        """Запустить воркер кластера"""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info(f"Started proxy cluster {self.proxy_id}")
    
    async def stop(self):
        """Остановить воркер кластера"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped proxy cluster {self.proxy_id}")
    
    async def _worker_loop(self):
        """Основной цикл обработки задач"""
        while self._running:
            try:
                # Ожидание задачи с таймаутом
                try:
                    task = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Проверка rate limit
                if (not task.bypass_adaptive_delay and 
                    self.state.rate_limit_until and datetime.now() < self.state.rate_limit_until):
                    # Вернуть задачу в очередь и подождать
                    await self._task_queue.put(task)
                    wait_time = (self.state.rate_limit_until - datetime.now()).total_seconds()
                    await asyncio.sleep(min(wait_time, 60))  # Максимум 60 секунд
                    continue
                
                # Проверка здоровья прокси
                if not self.state.is_healthy:
                    # Попробовать восстановить через некоторое время
                    await asyncio.sleep(30)
                    self.state.is_healthy = True
                    continue
                
                # Выполнить задачу
                await self._execute_task(task)
                
                # Применить задержку между запросами
                await self._apply_delay(task)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in proxy cluster {self.proxy_id} worker loop: {e}")
                await asyncio.sleep(1)
    
    async def _execute_task(self, task: ProfileTask):
        try:
            # Получить профиль
            profile = profile_manager.get_profile(task.profile_id)
            
            handler = self._action_handlers.get(task.action)
            if not handler:
                error_msg = f"No handler found for action {task.action}"
                logger.error(error_msg)
                self._priority_stats[task.priority]['errors'] += 1
                task.mark_failed(error_msg)
                return
            
            task.mark_started()
            start_time = datetime.now()
            
            # Передать profile в handler
            result = await handler(task, profile)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            success = result.get('success', True) if isinstance(result, dict) else True
            error_msg = result.get('error') if isinstance(result, dict) else None
            
            if success:
                task.mark_completed(result if isinstance(result, dict) else {'success': True, 'data': result})
            else:
                task.mark_failed(error_msg or "Task execution failed")
            
            await self._record_result(task, success, execution_time, error_msg)
            logger.debug(f"Executed task {task.task_id} on proxy {self.proxy_id} in {execution_time:.2f}s")
        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Error executing task {task.task_id} on proxy {self.proxy_id}: {e}")
            task.mark_failed(error_msg)
            await self._record_result(task, False, 0, error_msg)

    
    async def _record_result(self, task: ProfileTask, success: bool, 
                           execution_time: float, error: Optional[str] = None):
        """Записать результат выполнения задачи"""
        async with self._lock:
            self.state.last_request_time = datetime.now()
            
            if success:
                self.state.success_count += 1
                self._priority_stats[task.priority]['success'] += 1
                
                # Адаптивное уменьшение задержки при успехе
                if not task.bypass_adaptive_delay and self.state.success_count % 10 == 0:
                    self.state.current_delay = max(
                        self.state.current_delay * 0.95,  # Уменьшить на 5%
                        self.state.base_delay * 0.5  # Но не меньше 50% от базовой
                    )
            else:
                self.state.error_count += 1
                self._priority_stats[task.priority]['errors'] += 1
                
                # Адаптивное увеличение задержки при ошибках (только если не пропускаем)
                if not task.bypass_adaptive_delay:
                    if error and "429" in str(error) or "rate" in str(error).lower():
                        # Rate limit - увеличить задержку значительно
                        self.state.current_delay = min(
                            self.state.current_delay * 2.0,
                            8.0  # Максимум 8 секунд
                        )
                        # Установить время до которого нужно ждать
                        self.state.rate_limit_until = datetime.now() + timedelta(seconds=self.state.current_delay)
                        logger.warning(f"Rate limit detected on proxy {self.proxy_id}, increased delay to {self.state.current_delay}s")
                    
                    elif error and ("timeout" in str(error).lower() or "connection" in str(error).lower()):
                        # Проблемы с соединением
                        self.state.current_delay = min(
                            self.state.current_delay * 1.5,
                            8.0
                        )
                        self.state.is_healthy = False
                    else:
                        # Обычная ошибка
                        self.state.current_delay = min(
                            self.state.current_delay * 1.2,
                            3.0
                        )
                else:
                    # Если пропускаем адаптивные задержки, все равно отмечаем проблемы с соединением
                    if error and ("timeout" in str(error).lower() or "connection" in str(error).lower()):
                        self.state.is_healthy = False
    
    async def _apply_delay(self, task: ProfileTask):
        """Применить задержку между запросами с учетом флага bypass_adaptive_delay"""
        # Если задача пропускает адаптивную задержку
        if task.bypass_adaptive_delay:
            # Применяем только минимальную базовую задержку
            await asyncio.sleep(self.state.base_delay)
            return
        
        # Стандартная логика задержки
        delay = self.state.current_delay
        
        # Если есть активное ограничение по времени
        if self.state.rate_limit_until and datetime.now() < self.state.rate_limit_until:
            additional_delay = (self.state.rate_limit_until - datetime.now()).total_seconds()
            delay = max(delay, additional_delay)
        
        await asyncio.sleep(delay)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кластера"""
        async with self._lock:
            return {
                'proxy_id': self.proxy_id,
                'active_profiles': len(self.state.active_profiles),
                'profiles': self.state.active_profiles.copy(),
                'current_delay': self.state.current_delay,
                'base_delay': self.state.base_delay,
                'queue_size': self._task_queue.qsize(),
                'success_count': self.state.success_count,
                'error_count': self.state.error_count,
                'success_rate': self.state.success_count / (self.state.success_count + self.state.error_count) if (self.state.success_count + self.state.error_count) > 0 else 0,
                'is_healthy': self.state.is_healthy,
                'rate_limited_until': self.state.rate_limit_until.isoformat() if self.state.rate_limit_until else None,
                'last_request_time': self.state.last_request_time.isoformat() if self.state.last_request_time else None,
                'priority_stats': self._priority_stats.copy()
            }


class ClusterExecutor:
    """Менеджер кластеров прокси"""
    
    def __init__(self):
        self._clusters: Dict[str, Cluster] = {}
        self._profile_to_proxy: Dict[str, str] = {}
        self._action_handlers: Dict[str, Callable] = {}
        self._lock = asyncio.Lock()
        
        # Глобальная статистика
        self._global_stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'active_clusters': 0
        }
    
    def _ensure_future(self, task: ProfileTask) -> ProfileTask:
        """
        Убедиться что у задачи есть Future для получения результата.
        Создает Future только если его еще нет.
        """
        if not task.result_future:
            task.result_future = asyncio.Future()
        return task
    
    async def _add_task_to_cluster(self, profile_id: str, task: ProfileTask):
        """
        Внутренний метод для добавления задачи в кластер.
        Выделен отдельно для переиспользования.
        """
        proxy_id = self._profile_to_proxy.get(profile_id)
        if not proxy_id:
            raise ValueError(f"Profile {profile_id} is not assigned to any proxy")
        
        cluster = self._clusters.get(proxy_id)
        if not cluster:
            raise ValueError(f"No cluster found for proxy {proxy_id}")
        
        await cluster.add_task(task)
        self._global_stats['total_tasks'] += 1
    
    def register_action_handler(self, action: str, handler: Callable):
        """Регистрировать обработчик действия глобально"""
        self._action_handlers[action] = handler
        
        # Применить к существующим кластерам
        for cluster in self._clusters.values():
            cluster.register_action_handler(action, handler)
    
    async def get_or_create_cluster(self, proxy_id: str, base_delay: float = 1.0) -> Cluster:
        """Получить или создать кластер для прокси"""
        async with self._lock:
            if proxy_id not in self._clusters:
                cluster = Cluster(proxy_id, base_delay)
                
                # Зарегистрировать все обработчики
                for action, handler in self._action_handlers.items():
                    cluster.register_action_handler(action, handler)
                
                self._clusters[proxy_id] = cluster
                await cluster.start()
                self._global_stats['active_clusters'] += 1
                
                logger.info(f"Created and started new cluster for proxy {proxy_id}")
            
            return self._clusters[proxy_id]
    
    async def add_profile_to_proxy(self, profile_id: str, proxy_id: str, base_delay: float = 1.0):
        """Добавить профиль к прокси-кластеру"""
        # Удалить профиль из старого кластера, если был
        await self.remove_profile(profile_id)
        
        # Получить или создать кластер
        cluster = await self.get_or_create_cluster(proxy_id, base_delay)
        await cluster.add_profile(profile_id)
        
        self._profile_to_proxy[profile_id] = proxy_id
        logger.info(f"Added profile {profile_id} to proxy cluster {proxy_id}")
        
    async def select_best_proxy_id(self, proxy_ids: List[str]) -> Optional[str]:
        """Выбрать прокси с минимальным числом профилей (или без кластера вообще)"""
        best_proxy = None
        min_profiles = float("inf")

        async with self._lock:
            for proxy_id in proxy_ids:
                cluster = self._clusters.get(proxy_id)
                if not cluster:
                    # Если прокси ещё не используется — отдаем сразу
                    return proxy_id
                
                profile_count = len(cluster.state.active_profiles)
                if profile_count < min_profiles:
                    best_proxy = proxy_id
                    min_profiles = profile_count

        return best_proxy
    
    async def remove_profile(self, profile_id: str):
        """Удалить профиль из кластера"""
        proxy_id = self._profile_to_proxy.get(profile_id)
        if proxy_id and proxy_id in self._clusters:
            await self._clusters[proxy_id].remove_profile(profile_id)
            del self._profile_to_proxy[profile_id]
            
            # Если в кластере больше нет профилей, остановить его
            cluster = self._clusters[proxy_id]
            if len(cluster.state.active_profiles) == 0:
                await cluster.stop()
                del self._clusters[proxy_id]
                self._global_stats['active_clusters'] -= 1
                logger.info(f"Removed empty cluster for proxy {proxy_id}")
    
    async def submit_task(self, profile_id: str, task: ProfileTask) -> asyncio.Future:
        """
        Отправить задачу на выполнение и получить Future для результата.
        
        Args:
            profile_id: ID профиля
            task: Задача для выполнения
            
        Returns:
            Future который будет содержать результат выполнения
            
        Raises:
            ValueError: Если профиль не назначен или кластер не найден
        """
        task = self._ensure_future(task)
        
        try:
            await self._add_task_to_cluster(profile_id, task)
        except Exception as e:
            # Если не удалось добавить в кластер, сразу устанавливаем ошибку в Future
            if not task.result_future.done():
                task.result_future.set_exception(e)
        
        return task.result_future
    
    async def execute_task(self, profile_id: str, task: ProfileTask, 
                          timeout: Optional[float] = None) -> Any:
        """
        Выполнить задачу и дождаться результата.
        
        Args:
            profile_id: ID профиля
            task: Задача для выполнения  
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            Результат выполнения задачи
            
        Raises:
            asyncio.TimeoutError: Если превышен таймаут
            ValueError: Если профиль не назначен или кластер не найден
            Exception: Любая ошибка выполнения задачи
        """
        future = await self.submit_task(profile_id, task)
        
        if timeout:
            return await asyncio.wait_for(future, timeout=timeout)
        return await future
    
    async def add_task(self, profile_id: str, task: ProfileTask) -> asyncio.Future:
        """
        Добавить задачу для профиля (обратная совместимость).
        Теперь возвращает Future.
        """
        return await self.submit_task(profile_id, task)
    
    async def get_cluster_stats(self, proxy_id: str) -> Optional[Dict[str, Any]]:
        """Получить статистику кластера"""
        cluster = self._clusters.get(proxy_id)
        if cluster:
            return await cluster.get_stats()
        return None
    
    async def get_profile_proxy(self, profile_id: str) -> Optional[str]:
        """Получить прокси профиля"""
        return self._profile_to_proxy.get(profile_id)
    
    async def set_proxy_delay(self, proxy_id: str, base_delay: float):
        """Установить базовую задержку для прокси"""
        cluster = self._clusters.get(proxy_id)
        if cluster:
            async with cluster._lock:
                cluster.state.base_delay = base_delay
                cluster.state.current_delay = max(cluster.state.current_delay, base_delay)
            logger.info(f"Updated base delay for proxy {proxy_id} to {base_delay}s")
    
    async def get_all_stats(self) -> Dict[str, Any]:
        """Получить полную статистику всех кластеров"""
        cluster_stats = {}
        for proxy_id, cluster in self._clusters.items():
            cluster_stats[proxy_id] = await cluster.get_stats()
        
        return {
            'global_stats': self._global_stats,
            'clusters': cluster_stats,
            'profile_assignments': self._profile_to_proxy.copy()
        }
    
    async def shutdown(self):
        """Остановить все кластеры"""
        for cluster in self._clusters.values():
            await cluster.stop()
        self._clusters.clear()
        self._profile_to_proxy.clear()
        logger.info("Shutdown all proxy clusters")