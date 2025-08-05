
# app/execution/cluster_executor.py
import asyncio
import logging
from typing import Dict, Optional, Any, Callable, List
from datetime import datetime, timedelta

from app.models.execution_models import ProfileTask, TaskPriority, ProxyClusterState, StopTaskSentinel
from app.handlers.handlers_manager import BaseHandler, handlers_manager
from app.proxy.proxy_manager import proxy_manager

logger = logging.getLogger(__name__)

STOP_TASK = StopTaskSentinel()

class Cluster:
    """Кластер для одного прокси с общей очередью задач"""
    
    def __init__(self, proxy_id: str):
        self.proxy_id = proxy_id
        self.state = ProxyClusterState(proxy_id, [])
        
        # Общая очередь задач для всех профилей этого прокси
        self._task_queue = asyncio.PriorityQueue()
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Статистика по приоритетам
        self._priority_stats = {priority: {'count': 0, 'success': 0, 'errors': 0} 
                               for priority in TaskPriority}
    
    async def start(self):
        if self._worker_task and not self._worker_task.done():
            return
        
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info(f"Started proxy cluster {self.proxy_id}")
        
    async def add_task(self, task: ProfileTask):
        """Добавить задачу в очередь кластера"""
        await self._task_queue.put(task)
        self._priority_stats[task.priority]['count'] += 1
        logger.debug(f"Added task {task.task_id} to proxy cluster {self.proxy_id}")
    
    async def add_profile(self, profile_id: str):
        async with self._lock:
            if profile_id not in self.state.active_profiles:
                self.state.active_profiles.append(profile_id)
    
    async def _worker_loop(self):
        """Основной цикл обработки задач (с безопасной остановкой)"""
        logger.info(f"Worker loop started for proxy {self.proxy_id}")
        processed_tasks = 0
        
        while True:
            try:
                # Получаем задачу из очереди
                task = await self._task_queue.get()
                
                # Проверяем сигнал остановки
                if task is STOP_TASK:
                    logger.info(f"Received stop signal for proxy {self.proxy_id}, processed {processed_tasks} tasks")
                    break
                
                # Проверка rate limit
                if (not task.bypass_adaptive_delay and 
                    self.state.rate_limit_until and datetime.now() < self.state.rate_limit_until):
                    # Возвращаем задачу в очередь и ждем
                    await self._task_queue.put(task)
                    wait_time = (self.state.rate_limit_until - datetime.now()).total_seconds()
                    await asyncio.sleep(min(wait_time, 60))
                    continue
                
                # Проверка здоровья прокси
                if not self.state.is_healthy:
                    logger.warning(f"Proxy {self.proxy_id} is unhealthy, waiting...")
                    await asyncio.sleep(30)
                    self.state.is_healthy = True
                    continue
                
                # Выполнить задачу
                await self._execute_task(task)
                processed_tasks += 1
                
                # Применить задержку между запросами
                await self._apply_delay(task)
                
                # Отмечаем задачу как выполненную в очереди
                self._task_queue.task_done()
                
            except Exception as e:
                logger.exception(f"Error in proxy cluster {self.proxy_id} worker loop: {e}")
                # Если в цикле есть задача с Future, устанавливаем ошибку
                if 'task' in locals() and hasattr(task, 'result_future') and task.result_future and not task.result_future.done():
                    task.result_future.set_exception(e)
                
                # Отмечаем задачу как выполненную даже при ошибке
                try:
                    self._task_queue.task_done()
                except ValueError:
                    pass  # task_done() called too many times
                
                await asyncio.sleep(1)
        
        logger.info(f"Worker loop finished for proxy {self.proxy_id}")

    async def _execute_task(self, task: ProfileTask):
        """Выполнить задачу, обработать результат и записать статистику"""
        try:
            handler = self._get_handler(task)
            if handler is None:
                # Встановлюємо помилку в Future якщо він існує
                if task.result_future and not task.result_future.done():
                    task.result_future.set_exception(ValueError(f"No handler found for action {task.action}"))
                return

            task.mark_started()
            start_time = datetime.now()

            result = await self._run_handler(handler, task)

            success, error_msg = self._analyze_result(result)
            self._mark_task_result(task, success, result, error_msg)

            # Встановлюємо результат в Future
            if task.result_future and not task.result_future.done():
                if success:
                    task.result_future.set_result(result)
                else:
                    task.result_future.set_exception(Exception(error_msg or "Task execution failed"))

            execution_time = (datetime.now() - start_time).total_seconds()
            await self._record_result(task, success, execution_time, error_msg)

            logger.debug(f"Executed task {task.task_id} on proxy {self.proxy_id} in {execution_time:.2f}s")
        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Error executing task {task.task_id} on proxy {self.proxy_id}: {e}")
            task.mark_failed(error_msg)
            
            # Встановлюємо помилку в Future
            if task.result_future and not task.result_future.done():
                task.result_future.set_exception(e)
                
            await self._record_result(task, False, 0, error_msg)

    def _get_handler(self, task: ProfileTask) -> Optional[Callable]:
        handler = handlers_manager.get_handler(task.action)
        if not handler:
            error_msg = f"No handler found for action {task.action}"
            logger.error(error_msg)
            self._priority_stats[task.priority]['errors'] += 1
            task.mark_failed(error_msg)
            return None
        return handler

    async def _run_handler(self, handler: BaseHandler, task: ProfileTask) -> Any:
        return await handler(task)

    def _analyze_result(self, result: Any) -> tuple[bool, Optional[str]]:
        """
        Анализируем результат выполнения задачи
        result должен быть словарем с ключами 'success' и 'error'
        """
        if isinstance(result, dict):
            return result.get('success', True), result.get('error')
        return True, None

    def _mark_task_result(self, task: ProfileTask, success: bool, result: Any, error_msg: Optional[str]):
        if success:
            task.mark_completed(result if isinstance(result, dict) else {'success': True, 'data': result})
        else:
            task.mark_failed(error_msg or "Task execution failed")
    
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
                    if error and ("429" in str(error) or "rate" in str(error).lower()):
                        # Rate limit - увеличить задержку значительно
                        self.state.current_delay = min(
                            self.state.current_delay * 2.0,
                            16.0  # Максимум 16 секунд
                        )
                        # Установить время до которого нужно ждать
                        self.state.rate_limit_until = datetime.now() + timedelta(seconds=self.state.current_delay)
                        logger.warning(f"Rate limit detected on proxy {self.proxy_id}, increased delay to {self.state.current_delay}s")
                    
                    elif error and ("timeout" in str(error).lower() or "connection" in str(error).lower()):
                        # Проблемы с соединением
                        self.state.current_delay = min(
                            self.state.current_delay * 1.5,
                            16.0
                        )
                        self.state.is_healthy = False
                    else:
                        # Обычная ошибка
                        self.state.current_delay = min(
                            self.state.current_delay * 1.2,
                            16.0
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
       
    async def clear_queue(self):
        """Очистить очередь и установить ошибки для всех Future"""
        cleared_count = 0
        while not self._task_queue.empty():
            try:
                task = self._task_queue.get_nowait()
                if task is not STOP_TASK and hasattr(task, 'result_future') and task.result_future and not task.result_future.done():
                    task.result_future.set_exception(Exception("Cluster stopped"))
                    cleared_count += 1
            except asyncio.QueueEmpty:
                break
        
        if cleared_count > 0:
            logger.warning(f"Cleared {cleared_count} unfinished tasks from proxy {self.proxy_id}")
            
    async def stop(self):
        """Остановить кластер с корректным завершением задач"""
        # Добавляем сигнал остановки в конец очереди
        await self._task_queue.put(STOP_TASK)
        
        if self._worker_task:
            try:
                # Ждем завершения worker'а с таймаутом
                await asyncio.wait_for(self._worker_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning(f"Worker task for proxy {self.proxy_id} didn't finish in time, cancelling")
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                logger.exception(f"Error waiting for worker task: {e}")
            finally:
                self._worker_task = None
        
        # После завершения worker'а очищаем оставшиеся задачи
        await self.clear_queue()
        logger.info(f"Stopped proxy cluster {self.proxy_id}")


class ClusterExecutor:
    """Менеджер кластеров прокси"""
    
    def __init__(self):
        self._clusters: Dict[str, Cluster] = {}
        self._profile_to_proxy: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        
        # Глобальная статистика
        self._global_stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'active_clusters': 0
        }
        
    async def submit_task(self, task: ProfileTask) -> asyncio.Future:
        """
        Отправить задачу на выполнение и получить Future для результата.
        
        Args:
            task: Задача для выполнения
            
        Returns:
            Future который будет содержать результат выполнения
            
        Raises:
            ValueError: Если профиль не назначен или кластер не найден
        """
        task = self._ensure_future(task)
        try:
            await self._add_task_to_cluster(task)
        except Exception as e:
            if not task.result_future.done():
                task.result_future.set_exception(e)
        return task.result_future
    
    async def execute_task(self, task: ProfileTask, 
                          timeout: Optional[float] = None) -> Any:
        """
        Выполнить задачу и дождаться результата.
        
        Args:
            task: Задача для выполнения  
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            Результат выполнения задачи
            
        Raises:
            asyncio.TimeoutError: Если превышен таймаут
            ValueError: Если профиль не назначен или кластер не найден
            Exception: Любая ошибка выполнения задачи
        """
        
        future = await self.submit_task(task)

        if timeout:
            result = await asyncio.wait_for(future, timeout=timeout)
        else:
            result = await future

        return result
    
    async def assign_profile(self, profile_id: str, proxy_id: str = None):
        """Назначить профиль один раз."""
        return await self._ensure_profile_assigned(profile_id, proxy_id)
    
    async def _ensure_profile_assigned(self, profile_id: str, proxy_id: str = None):
        """Убедиться, что профиль назначен на прокси."""
        current_proxy = self._profile_to_proxy.get(profile_id)
        
        if current_proxy:
            return current_proxy  # Уже назначен
        
        # Назначить на указанный или выбрать лучший
        if not proxy_id:
            proxy_id = await self.select_best_proxy_id(proxy_manager.all_proxy_ids)

        cluster = await self._get_or_create_cluster(proxy_id)
        
        await cluster.add_profile(profile_id)
        self._profile_to_proxy[profile_id] = proxy_id
        return proxy_id
    
    async def assign_profiles_to_proxy(self, profile_ids: list, proxy_id: str):
        """Назначить несколько профилей на один прокси."""
        cluster = await self._get_or_create_cluster(proxy_id)

        reassigned = 0
        for profile_id in profile_ids:
            current_proxy = self._profile_to_proxy.get(profile_id)

            if current_proxy == proxy_id:
                continue  # Уже назначен на нужный прокси

            if current_proxy:
                await self._remove_profile_from_proxy(profile_id, current_proxy)
                reassigned += 1

            await cluster.add_profile(profile_id)
            self._profile_to_proxy[profile_id] = proxy_id

        logger.info(f"Reassigned {reassigned} profiles to proxy cluster {proxy_id}")

    async def _add_task_to_cluster(self, task: ProfileTask):
        """Добавить задачу в кластер, убедившись, что кластер существует."""
        cluster = await self._get_or_create_cluster(task.proxy_id)
        await cluster.add_task(task)
        self._global_stats['total_tasks'] += 1
    
    async def _get_or_create_cluster(self, proxy_id: str) -> Cluster:
        """Получить или создать кластер для прокси"""
        async with self._lock:
            if proxy_id not in self._clusters:
                cluster = Cluster(proxy_id)
                self._clusters[proxy_id] = cluster
                await cluster.start()
                self._global_stats['active_clusters'] += 1
                logger.info(f"Created and started new cluster for proxy {proxy_id}")
                
            return self._clusters[proxy_id]
            
    def _ensure_future(self, task: ProfileTask) -> ProfileTask:
        """
        Убедиться что у задачи есть Future для получения результата.
        Создает Future только если его еще нет.
        """
        if not task.result_future:
            task.result_future = asyncio.Future()
        return task
    
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
    
    async def get_cluster_stats(self, proxy_id: str) -> Optional[Dict[str, Any]]:
        """Получить статистику кластера"""
        cluster = self._clusters.get(proxy_id)
        if cluster:
            return await cluster.get_stats()
        return None
    
    async def get_profile_proxy(self, profile_id: str) -> Optional[str]:
        """Получить прокси профиля"""
        return self._profile_to_proxy.get(profile_id)
    
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
        
    async def get_profile_cluster_info(self, profile_id: str) -> dict:
        """
        Получить информацию о кластере профиля.
        """
        proxy_id = self._profile_to_proxy.get(profile_id)
        if not proxy_id:
            return {"assigned": False}
        
        cluster_stats = await self.get_cluster_stats(proxy_id)
        return {
            "assigned": True,
            "proxy_id": proxy_id,
            "cluster_stats": cluster_stats
        }
    
    async def shutdown(self):
        """Остановить все кластеры"""
        logger.info(f"Shutting down {len(self._clusters)} clusters...")
        
        # Останавливаем все кластеры параллельно
        stop_tasks = []
        for proxy_id, cluster in self._clusters.items():
            stop_task = asyncio.create_task(cluster.stop())
            stop_tasks.append(stop_task)
        
        if stop_tasks:
            # Ждем завершения всех кластеров
            try:
                await asyncio.gather(*stop_tasks, return_exceptions=True)
            except Exception as e:
                logger.exception(f"Error during cluster shutdown: {e}")
        
        self._clusters.clear()
        self._profile_to_proxy.clear()
        logger.info("All proxy clusters shut down")