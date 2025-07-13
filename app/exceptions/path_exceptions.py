from __future__ import annotations
from typing import Callable, Optional

from app.exceptions.base_exceptions import AppError, ProfileException


class AppConfigMissingException(AppError):
    """Ошибка, возникающая при отсутствии конфигурации приложения."""

    def __init__(self, message: str = "App config is missing.", *, code: int = 500, on_error: Optional[Callable] = None):
        super().__init__(message, code=code, on_error=on_error)
        
        
class ProfileDirNotFoundException(ProfileException):
    """Profile not found."""

    def __init__(self, message: str = "Profile not found.", *, code: int = 404, on_error: Optional[Callable] = None):
        super().__init__(message, code=code, on_error=on_error)