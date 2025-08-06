# app/execution/cluster_executor.py
import asyncio
import logging
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta

from app.models.execution_models import ProfileTask, TaskPriority, ProxyClusterState, StopTaskSentinel
from app.execution.managers.handlers_manager import BaseHandler, handlers_manager
from app.proxy.proxy_manager import proxy_manager

logger = logging.getLogger(__name__)

STOP_TASK = StopTaskSentinel()


class TaskExecutionResult:
    """Encapsulates task execution result"""
    
    def __init__(self, success: bool, result: Any = None, error: Optional[str] = None):
        self.success = success
        self.result = result
        self.error = error


class PriorityStats:
    """Statistics for task priorities"""
    
    def __init__(self):
        self._stats = {priority: {'count': 0, 'success': 0, 'errors': 0} 
                      for priority in TaskPriority}
    
    def increment_count(self, priority: TaskPriority):
        self._stats[priority]['count'] += 1
    
    def increment_success(self, priority: TaskPriority):
        self._stats[priority]['success'] += 1
    
    def increment_errors(self, priority: TaskPriority):
        self._stats[priority]['errors'] += 1
    
    def get_stats(self) -> Dict:
        return self._stats.copy()


class TaskDelayCalculator:
    """Calculates delays between tasks based on proxy state"""
    
    @staticmethod
    def calculate_delay(proxy_state: ProxyClusterState, task: ProfileTask) -> float:
        if task.bypass_adaptive_delay:
            return proxy_state.base_delay
        
        delay = proxy_state.current_delay
        
        if TaskDelayCalculator._has_active_rate_limit(proxy_state):
            additional_delay = TaskDelayCalculator._calculate_rate_limit_delay(proxy_state)
            delay = max(delay, additional_delay)
        
        return delay
    
    @staticmethod
    def _has_active_rate_limit(proxy_state: ProxyClusterState) -> bool:
        return (proxy_state.rate_limit_until and 
                datetime.now() < proxy_state.rate_limit_until)
    
    @staticmethod
    def _calculate_rate_limit_delay(proxy_state: ProxyClusterState) -> float:
        return (proxy_state.rate_limit_until - datetime.now()).total_seconds()


class ProxyStateManager:
    """Manages proxy state updates based on task execution results"""
    
    RATE_LIMIT_KEYWORDS = ["429", "rate"]
    CONNECTION_ERROR_KEYWORDS = ["timeout", "connection"]
    
    MAX_DELAY = 16.0
    DELAY_DECREASE_FACTOR = 0.95
    DELAY_DECREASE_THRESHOLD = 10
    DELAY_INCREASE_RATE_LIMIT = 2.0
    DELAY_INCREASE_CONNECTION = 1.5
    DELAY_INCREASE_GENERAL = 1.2
    
    def __init__(self, state: ProxyClusterState, priority_stats: PriorityStats):
        self._state = state
        self._priority_stats = priority_stats
    
    async def update_state(self, task: ProfileTask, execution_result: TaskExecutionResult):
        """Update proxy state based on task execution result"""
        async with asyncio.Lock():
            self._state.last_request_time = datetime.now()
            
            if execution_result.success:
                await self._handle_success(task)
            else:
                await self._handle_failure(task, execution_result.error)
    
    async def _handle_success(self, task: ProfileTask):
        self._state.success_count += 1
        self._priority_stats.increment_success(task.priority)
        
        if not task.bypass_adaptive_delay and self._should_decrease_delay():
            self._decrease_delay()
    
    async def _handle_failure(self, task: ProfileTask, error: Optional[str]):
        self._state.error_count += 1
        self._priority_stats.increment_errors(task.priority)
        
        if not task.bypass_adaptive_delay:
            self._adjust_delay_on_error(error)
        elif self._is_connection_error(error):
            self._state.is_healthy = False
    
    def _should_decrease_delay(self) -> bool:
        return self._state.success_count % self.DELAY_DECREASE_THRESHOLD == 0
    
    def _decrease_delay(self):
        min_delay = self._state.base_delay * 0.5
        self._state.current_delay = max(
            self._state.current_delay * self.DELAY_DECREASE_FACTOR,
            min_delay
        )
    
    def _adjust_delay_on_error(self, error: Optional[str]):
        if self._is_rate_limit_error(error):
            self._handle_rate_limit_error()
        elif self._is_connection_error(error):
            self._handle_connection_error()
        else:
            self._handle_general_error()
    
    def _is_rate_limit_error(self, error: Optional[str]) -> bool:
        if not error:
            return False
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in self.RATE_LIMIT_KEYWORDS)
    
    def _is_connection_error(self, error: Optional[str]) -> bool:
        if not error:
            return False
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in self.CONNECTION_ERROR_KEYWORDS)
    
    def _handle_rate_limit_error(self):
        self._state.current_delay = min(
            self._state.current_delay * self.DELAY_INCREASE_RATE_LIMIT,
            self.MAX_DELAY
        )
        self._state.rate_limit_until = datetime.now() + timedelta(seconds=self._state.current_delay)
        logger.warning(f"Rate limit detected, increased delay to {self._state.current_delay}s")
    
    def _handle_connection_error(self):
        self._state.current_delay = min(
            self._state.current_delay * self.DELAY_INCREASE_CONNECTION,
            self.MAX_DELAY
        )
        self._state.is_healthy = False
    
    def _handle_general_error(self):
        self._state.current_delay = min(
            self._state.current_delay * self.DELAY_INCREASE_GENERAL,
            self.MAX_DELAY
        )


class TaskHandler:
    """Handles task execution and result processing"""
    
    def __init__(self, proxy_id: str):
        self.proxy_id = proxy_id
    
    async def execute_task(self, task: ProfileTask) -> TaskExecutionResult:
        """Execute a single task and return the result"""
        try:
            handler = self._get_handler(task)
            if not handler:
                return TaskExecutionResult(False, None, f"No handler found for action {task.action}")
            
            task.mark_started()
            result = await self._run_handler(handler, task)
            
            success, error_msg = self._analyze_result(result)
            
            if success:
                task.mark_completed(self._format_result(result))
            else:
                task.mark_failed(error_msg or "Task execution failed")
            
            return TaskExecutionResult(success, result, error_msg)
            
        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Error executing task {task.task_id} on proxy {self.proxy_id}: {e}")
            task.mark_failed(error_msg)
            return TaskExecutionResult(False, None, error_msg)
    
    def _get_handler(self, task: ProfileTask) -> Optional[BaseHandler]:
        handler = handlers_manager.get_handler(task.action)
        if not handler:
            logger.error(f"No handler found for action {task.action}")
        return handler
    
    async def _run_handler(self, handler: BaseHandler, task: ProfileTask) -> Any:
        return await handler(task)
    
    def _analyze_result(self, result: Any) -> Tuple[bool, Optional[str]]:
        """Analyze task execution result"""
        if isinstance(result, dict):
            return result.get('success', True), result.get('error')
        return True, None
    
    def _format_result(self, result: Any) -> Dict[str, Any]:
        if isinstance(result, dict):
            return result
        return {'success': True, 'data': result}


class Cluster:
    """Cluster for one proxy with shared task queue"""
    
    HEALTH_CHECK_DELAY = 30
    RATE_LIMIT_RECHECK_DELAY = 60
    
    def __init__(self, proxy_id: str):
        self.proxy_id = proxy_id
        self.state = ProxyClusterState(proxy_id, [])
        
        self._task_queue = asyncio.PriorityQueue()
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        self._priority_stats = PriorityStats()
        self._state_manager = ProxyStateManager(self.state, self._priority_stats)
        self._task_handler = TaskHandler(proxy_id)
    
    async def start(self):
        """Start the cluster worker"""
        if self._worker_task and not self._worker_task.done():
            return
        
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info(f"Started proxy cluster {self.proxy_id}")
    
    async def add_task(self, task: ProfileTask):
        """Add task to cluster queue"""
        await self._task_queue.put(task)
        self._priority_stats.increment_count(task.priority)
        logger.debug(f"Added task {task.task_id} to proxy cluster {self.proxy_id}")
    
    async def add_profile(self, profile_id: str):
        """Add profile to cluster"""
        async with self._lock:
            if profile_id not in self.state.active_profiles:
                self.state.active_profiles.append(profile_id)
    
    async def _worker_loop(self):
        """Main task processing loop"""
        logger.info(f"Worker loop started for proxy {self.proxy_id}")
        processed_tasks = 0
        
        while True:
            try:
                task = await self._get_next_task()
                if task is STOP_TASK:
                    logger.info(f"Received stop signal for proxy {self.proxy_id}, processed {processed_tasks} tasks")
                    break
                
                if await self._should_skip_task(task):
                    continue
                
                await self._process_task(task)
                processed_tasks += 1
                
                self._task_queue.task_done()
                
            except Exception as e:
                logger.exception(f"Error in proxy cluster {self.proxy_id} worker loop: {e}")
                await self._handle_worker_error(e)
                await asyncio.sleep(1)
        
        logger.info(f"Worker loop finished for proxy {self.proxy_id}")
    
    async def _get_next_task(self) -> ProfileTask:
        return await self._task_queue.get()
    
    async def _should_skip_task(self, task: ProfileTask) -> bool:
        """Check if task should be skipped due to rate limiting or health issues"""
        if await self._is_rate_limited(task):
            await self._handle_rate_limited_task(task)
            return True
        
        if not self.state.is_healthy:
            await self._handle_unhealthy_proxy()
            return True
        
        return False
    
    async def _is_rate_limited(self, task: ProfileTask) -> bool:
        return (not task.bypass_adaptive_delay and 
                self.state.rate_limit_until and 
                datetime.now() < self.state.rate_limit_until)
    
    async def _handle_rate_limited_task(self, task: ProfileTask):
        await self._task_queue.put(task)
        wait_time = TaskDelayCalculator._calculate_rate_limit_delay(self.state)
        await asyncio.sleep(min(wait_time, self.RATE_LIMIT_RECHECK_DELAY))
    
    async def _handle_unhealthy_proxy(self):
        logger.warning(f"Proxy {self.proxy_id} is unhealthy, waiting...")
        await asyncio.sleep(self.HEALTH_CHECK_DELAY)
        self.state.is_healthy = True
    
    async def _process_task(self, task: ProfileTask):
        """Process a single task"""
        start_time = datetime.now()
        
        execution_result = await self._task_handler.execute_task(task)
        
        await self._handle_task_result(task, execution_result)
        await self._apply_delay(task)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.debug(f"Executed task {task.task_id} on proxy {self.proxy_id} in {execution_time:.2f}s")
    
    async def _handle_task_result(self, task: ProfileTask, execution_result: TaskExecutionResult):
        """Handle task execution result"""
        if task.result_future and not task.result_future.done():
            if execution_result.success:
                task.result_future.set_result(execution_result.result)
            else:
                task.result_future.set_exception(Exception(execution_result.error or "Task execution failed"))
        
        await self._state_manager.update_state(task, execution_result)
    
    async def _handle_worker_error(self, error: Exception):
        """Handle worker loop errors"""
        if 'task' in locals():
            task = locals()['task']
            if (hasattr(task, 'result_future') and 
                task.result_future and 
                not task.result_future.done()):
                task.result_future.set_exception(error)
        
        try:
            self._task_queue.task_done()
        except ValueError:
            pass  # task_done() called too many times
    
    async def _apply_delay(self, task: ProfileTask):
        """Apply delay between requests"""
        delay = TaskDelayCalculator.calculate_delay(self.state, task)
        await asyncio.sleep(delay)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cluster statistics"""
        async with self._lock:
            total_requests = self.state.success_count + self.state.error_count
            success_rate = (self.state.success_count / total_requests) if total_requests > 0 else 0
            
            return {
                'proxy_id': self.proxy_id,
                'active_profiles': len(self.state.active_profiles),
                'profiles': self.state.active_profiles.copy(),
                'current_delay': self.state.current_delay,
                'base_delay': self.state.base_delay,
                'queue_size': self._task_queue.qsize(),
                'success_count': self.state.success_count,
                'error_count': self.state.error_count,
                'success_rate': success_rate,
                'is_healthy': self.state.is_healthy,
                'rate_limited_until': self._format_datetime(self.state.rate_limit_until),
                'last_request_time': self._format_datetime(self.state.last_request_time),
                'priority_stats': self._priority_stats.get_stats()
            }
    
    def _format_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        return dt.isoformat() if dt else None
    
    async def clear_queue(self):
        """Clear queue and set errors for all futures"""
        cleared_count = 0
        while not self._task_queue.empty():
            try:
                task = self._task_queue.get_nowait()
                if self._should_clear_task(task):
                    task.result_future.set_exception(Exception("Cluster stopped"))
                    cleared_count += 1
            except asyncio.QueueEmpty:
                break
        
        if cleared_count > 0:
            logger.warning(f"Cleared {cleared_count} unfinished tasks from proxy {self.proxy_id}")
    
    def _should_clear_task(self, task) -> bool:
        return (task is not STOP_TASK and 
                hasattr(task, 'result_future') and 
                task.result_future and 
                not task.result_future.done())
    
    async def stop(self):
        """Stop cluster with graceful task completion"""
        await self._task_queue.put(STOP_TASK)
        
        if self._worker_task:
            await self._stop_worker_task()
        
        await self.clear_queue()
        logger.info(f"Stopped proxy cluster {self.proxy_id}")
    
    async def _stop_worker_task(self):
        """Stop worker task with timeout"""
        try:
            await asyncio.wait_for(self._worker_task, timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning(f"Worker task for proxy {self.proxy_id} didn't finish in time, cancelling")
            self._worker_task.cancel()
            await self._wait_for_cancellation()
        except Exception as e:
            logger.exception(f"Error waiting for worker task: {e}")
        finally:
            self._worker_task = None
    
    async def _wait_for_cancellation(self):
        """Wait for worker task cancellation"""
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass


class GlobalStats:
    """Global statistics tracker"""
    
    def __init__(self):
        self._stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'active_clusters': 0
        }
    
    def increment_total_tasks(self):
        self._stats['total_tasks'] += 1
    
    def increment_active_clusters(self):
        self._stats['active_clusters'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        return self._stats.copy()
    
    def reset(self):
        self._stats = {key: 0 for key in self._stats}


class ClusterManager:
    """Manager of proxy clusters"""
    
    def __init__(self):
        self._clusters: Dict[str, Cluster] = {}
        self._profile_to_proxy: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._global_stats = GlobalStats()
    
    async def submit_task(self, task: ProfileTask) -> asyncio.Future:
        """Submit task for execution and get future for result"""
        task = self._ensure_future(task)
        try:
            await self._add_task_to_cluster(task)
        except Exception as e:
            if not task.result_future.done():
                task.result_future.set_exception(e)
        return task.result_future
    
    async def execute_task(self, task: ProfileTask, timeout: Optional[float] = None) -> Any:
        """Execute task and wait for result"""
        future = await self.submit_task(task)
        
        if timeout:
            return await asyncio.wait_for(future, timeout=timeout)
        return await future
    
    async def assign_profile(self, profile_id: str, proxy_id: str = None) -> str:
        """Assign profile once"""
        return await self._ensure_profile_assigned(profile_id, proxy_id)
    
    async def assign_profiles_to_proxy(self, profile_ids: List[str], proxy_id: str):
        """Assign multiple profiles to one proxy"""
        cluster = await self._get_or_create_cluster(proxy_id)
        reassigned = 0
        
        for profile_id in profile_ids:
            if await self._reassign_profile_if_needed(profile_id, proxy_id, cluster):
                reassigned += 1
        
        logger.info(f"Reassigned {reassigned} profiles to proxy cluster {proxy_id}")
    
    async def _ensure_profile_assigned(self, profile_id: str, proxy_id: str = None) -> str:
        """Ensure profile is assigned to a proxy"""
        current_proxy = self._profile_to_proxy.get(profile_id)
        
        if current_proxy:
            return current_proxy
        
        if not proxy_id:
            proxy_id = await self.select_best_proxy_id(proxy_manager.all_proxy_ids)
        
        cluster = await self._get_or_create_cluster(proxy_id)
        await cluster.add_profile(profile_id)
        self._profile_to_proxy[profile_id] = proxy_id
        
        return proxy_id
    
    async def _reassign_profile_if_needed(self, profile_id: str, target_proxy_id: str, target_cluster: Cluster) -> bool:
        """Reassign profile if it's assigned to different proxy"""
        current_proxy = self._profile_to_proxy.get(profile_id)
        
        if current_proxy == target_proxy_id:
            return False
        
        if current_proxy:
            await self._remove_profile_from_proxy(profile_id, current_proxy)
        
        await target_cluster.add_profile(profile_id)
        self._profile_to_proxy[profile_id] = target_proxy_id
        
        return True
    
    async def _add_task_to_cluster(self, task: ProfileTask):
        """Add task to cluster, ensuring cluster exists"""
        cluster = await self._get_or_create_cluster(task.proxy_id)
        await cluster.add_task(task)
        self._global_stats.increment_total_tasks()
    
    async def _get_or_create_cluster(self, proxy_id: str) -> Cluster:
        """Get or create cluster for proxy"""
        async with self._lock:
            if proxy_id not in self._clusters:
                cluster = Cluster(proxy_id)
                self._clusters[proxy_id] = cluster
                await cluster.start()
                self._global_stats.increment_active_clusters()
                logger.info(f"Created and started new cluster for proxy {proxy_id}")
            
            return self._clusters[proxy_id]
    
    def _ensure_future(self, task: ProfileTask) -> ProfileTask:
        """Ensure task has future for getting result"""
        if not task.result_future:
            task.result_future = asyncio.Future()
        return task
    
    async def select_best_proxy_id(self, proxy_ids: List[str]) -> Optional[str]:
        """Select proxy with minimum number of profiles"""
        best_proxy = None
        min_profiles = float("inf")
        
        async with self._lock:
            for proxy_id in proxy_ids:
                cluster = self._clusters.get(proxy_id)
                if not cluster:
                    return proxy_id  # Unused proxy is best choice
                
                profile_count = len(cluster.state.active_profiles)
                if profile_count < min_profiles:
                    best_proxy = proxy_id
                    min_profiles = profile_count
        
        return best_proxy
    
    async def _remove_profile_from_proxy(self, profile_id: str, proxy_id: str):
        """Remove profile from proxy cluster"""
        cluster = self._clusters.get(proxy_id)
        if cluster and profile_id in cluster.state.active_profiles:
            cluster.state.active_profiles.remove(profile_id)
    
    # Statistics and info methods
    async def get_cluster_stats(self, proxy_id: str) -> Optional[Dict[str, Any]]:
        """Get cluster statistics"""
        cluster = self._clusters.get(proxy_id)
        return await cluster.get_stats() if cluster else None
    
    async def get_profile_proxy(self, profile_id: str) -> Optional[str]:
        """Get profile's proxy"""
        return self._profile_to_proxy.get(profile_id)
    
    async def get_all_stats(self) -> Dict[str, Any]:
        """Get complete statistics of all clusters"""
        cluster_stats = {}
        for proxy_id, cluster in self._clusters.items():
            cluster_stats[proxy_id] = await cluster.get_stats()
        
        return {
            'global_stats': self._global_stats.get_stats(),
            'clusters': cluster_stats,
            'profile_assignments': self._profile_to_proxy.copy()
        }
    
    async def get_profile_cluster_info(self, profile_id: str) -> Dict[str, Any]:
        """Get profile's cluster information"""
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
        """Stop all clusters"""
        logger.info(f"Shutting down {len(self._clusters)} clusters...")
        
        stop_tasks = [
            asyncio.create_task(cluster.stop()) 
            for cluster in self._clusters.values()
        ]
        
        if stop_tasks:
            try:
                await asyncio.gather(*stop_tasks, return_exceptions=True)
            except Exception as e:
                logger.exception(f"Error during cluster shutdown: {e}")
        
        self._clusters.clear()
        self._profile_to_proxy.clear()
        self._global_stats.reset()
        logger.info("All proxy clusters shut down")