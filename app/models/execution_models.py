# app/execution/models/execution_models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

class ExecutionMode(Enum):
    """Режимы выполнения"""
    ASYNC_TASKS = "async_tasks"
    SEPARATE_PROCESSES = "separate_processes"

class ProfileStatus(Enum):
    """Статусы профиля"""
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    ERROR = "error"

class TaskPriority(Enum):
    """Приоритеты задач"""
    CRITICAL = 1    # Критические задачи (аварийные операции)
    HIGH = 2        # Высокий приоритет (срочные операции)
    NORMAL = 3      # Обычный приоритет (стандартные операции)
    LOW = 4         # Низкий приоритет (отложенные операции)
    BACKGROUND = 5  # Фоновые задачи

@dataclass
class ProfileTask:
    """Задача для выполнения профилем"""
    profile_id: str
    action: str
    params: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = None
    scheduled_at: Optional[datetime] = None  # Запланированное время выполнения
    max_retries: int = 3
    retry_count: int = 0
    dependencies: List[str] = None  # ID задач, которые должны выполниться первыми
    task_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.dependencies is None:
            self.dependencies = []
        if self.task_id is None:
            import uuid
            self.task_id = str(uuid.uuid4())
    
    def __lt__(self, other):
        """Сравнение для сортировки по приоритету"""
        if not isinstance(other, ProfileTask):
            return NotImplemented
        
        # Сначала сравниваем по приоритету (меньшее число = выше приоритет)
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        
        # Затем по времени создания (раньше = выше приоритет)
        return self.created_at < other.created_at
    
    def can_execute(self, completed_tasks: set) -> bool:
        """Проверить, можно ли выполнить задачу"""
        # Проверить зависимости
        if self.dependencies:
            for dep_id in self.dependencies:
                if dep_id not in completed_tasks:
                    return False
        
        # Проверить запланированное время
        if self.scheduled_at and datetime.now() < self.scheduled_at:
            return False
        
        return True

@dataclass
class ProfileExecutionState:
    """Состояние выполнения профиля"""
    profile_id: str
    status: ProfileStatus
    started_at: datetime
    last_activity: datetime
    current_action: Optional[str] = None
    success_count: int = 0
    error_count: int = 0
    pending_tasks: int = 0
    current_task_priority: Optional[TaskPriority] = None
    completed_tasks: set = None
    
    def __post_init__(self):
        if self.completed_tasks is None:
            self.completed_tasks = set()

@dataclass
class DelayConfig:
    """Конфігурація задержек"""
    base_delay: float = 2.0
    max_delay: float = 60.0
    success_divider: float = 1.1
    error_multiplier: float = 1.5
    priority_multipliers: Dict[TaskPriority, float] = None
    enable_profile_delay: bool = True  

    def __post_init__(self):
        if self.priority_multipliers is None:
            self.priority_multipliers = {
                TaskPriority.CRITICAL: 0.1,
                TaskPriority.HIGH: 0.5,
                TaskPriority.NORMAL: 1.0,
                TaskPriority.LOW: 1.5,
                TaskPriority.BACKGROUND: 2.0
            }

@dataclass
class ProxyDelayState:
    """Состояние задержек для прокси"""
    proxy_id: str
    current_delay: float = 2.0
    base_delay: float = 2.0
    last_request_time: Optional[datetime] = None
    success_count: int = 0
    error_count: int = 0
    active_profiles: List[str] = None

    def __post_init__(self):
        if self.active_profiles is None:
            self.active_profiles = []