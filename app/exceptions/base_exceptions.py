from typing import Callable, Optional

class AppError(Exception):
    """Базовая ошибка приложения."""

    def __init__(self, message: str, *, code: int = 500, on_error: Optional[Callable] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.on_error = on_error

    def handle(self):
        """Вызывается при обработке ошибки, если задан on_error."""
        if self.on_error:
            self.on_error()
            
    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other
        
        
class DataBaseException(AppError):
    """Базовое исключение для ошибок базы данных."""
        
        
class ProfileException(AppError):
    """Базовая ошибка для профилей."""
    
    
class ProfileRegistrationException(ProfileException):
    """Базовая ошибка для сетевых конфигураций профилей."""