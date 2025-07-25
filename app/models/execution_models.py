# app/execution/models/execution_models.py
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import uuid

class TaskStatus(Enum):
    """Статусы задач"""
    PENDING = "pending"      # Ожидает выполнения
    PROCESSING = "processing" # Выполняется
    COMPLETED = "completed"   # Выполнена успешно
    FAILED = "failed"        # Выполнена с ошибкой
    CANCELLED = "cancelled"   # Отменена

class TaskPriority(Enum):
    """Приоритеты задач"""
    CRITICAL = 1  
    HIGH = 2        
    NORMAL = 3      
    LOW = 4         
    BACKGROUND = 5  
    
@dataclass
class ProxyClusterState:
    """Состояние кластера прокси"""
    proxy_id: str
    active_profiles: List[str]
    current_delay: float = 1.0
    base_delay: float = 1.0
    last_request_time: Optional[datetime] = None
    success_count: int = 0
    error_count: int = 0
    rate_limit_until: Optional[datetime] = None
    is_healthy: bool = True

@dataclass
class ProfileTask:
    """
    Задача для выполнения в рамках профиля через прокси кластер
    
    Используется для организации очереди задач с приоритизацией
    и отслеживания выполнения действий в системе управления профилями.
    """
    
    # Основные поля
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    profile_id: str = ""           # ID профиля, для которого выполняется задача
    action: str = ""               # Тип действия (например, "login", "scrape", "post")
    priority: TaskPriority = TaskPriority.NORMAL
    
    # Данные для выполнения
    payload: Dict[str, Any] = field(default_factory=dict)  # Параметры для выполнения действия
    
    # Метаданные
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None  # Когда задача должна быть выполнена
    attempts: int = 0                        # Количество попыток выполнения
    max_attempts: int = 3                    # Максимальное количество попыток
    
    # Результат выполнения
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Дополнительные параметры
    timeout: float = 30.0                    # Таймаут выполнения в секундах
    retry_delay: float = 5.0                 # Задержка между повторными попытками
    bypass_adaptive_delay: bool = False      # Пропустить адаптивную задержку для этой задачи
    
    # Future для асинхронного получения результата
    result_future: Optional[asyncio.Future] = field(default=None, init=False)
    
    def __lt__(self, other):
        """Сравнение для PriorityQueue (меньший приоритет = выше в очереди)"""
        if not isinstance(other, ProfileTask):
            return NotImplemented
        
        # Сначала сравниваем по приоритету
        if self.priority != other.priority:
            return self.priority < other.priority
        
        # Если приоритеты равны, сравниваем по времени создания
        return self.created_at < other.created_at
    
    def can_retry(self) -> bool:
        """Проверить, можно ли повторить задачу"""
        return self.attempts < self.max_attempts and self.status == TaskStatus.FAILED
    
    def mark_started(self):
        """Отметить начало выполнения"""
        self.status = TaskStatus.PROCESSING
        self.started_at = datetime.now()
        self.attempts += 1
    
    def mark_completed(self, result: Dict[str, Any]):
        """Отметить успешное завершение"""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now()
        
        # Установить результат в Future, если он существует
        if self.result_future and not self.result_future.done():
            self.result_future.set_result(result)
    
    def mark_failed(self, error: str):
        """Отметить неудачное завершение"""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()
        
        # Установить ошибку в Future, если он существует
        if self.result_future and not self.result_future.done():
            self.result_future.set_exception(Exception(error))
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для сериализации"""
        return {
            'task_id': self.task_id,
            'profile_id': self.profile_id,
            'action': self.action,
            'priority': self.priority.value,
            'payload': self.payload,
            'created_at': self.created_at.isoformat(),
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'status': self.status.value,
            'result': self.result,
            'error': self.error,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'timeout': self.timeout,
            'retry_delay': self.retry_delay
        }