class AppError(Exception):
    """Базовая ошибка приложения."""

    def __init__(self, message: str, *, code: int = 500, on_error: callable | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.on_error = on_error

    def handle(self):
        """Вызывается при обработке ошибки, если задан on_error."""
        if self.on_error:
            self.on_error()


class ProfileException(AppError):
    """Базовая ошибка для профилей."""


class ProfileDirNotFoundError(ProfileException):
    """Profile not found."""

    def __init__(self, message: str = "Profile not found.", *, code: int = 404, on_error: callable | None = None):
        super().__init__(message, code=code, on_error=on_error)
        
        
class ProfileNetworkConfigNotFoundError(ProfileException):
    """Network config not found."""

    def __init__(self, message: str = "Network config not found.", *, code: int = 404, on_error: callable | None = None):
        super().__init__(message, code=code, on_error=on_error)
        

class ProfileNetworkConfigEmptyError(ProfileException):
    """Network config empty."""

    def __init__(self, message: str = "Network config empty.", *, code: int = 404, on_error: callable | None = None):
        super().__init__(message, code=code, on_error=on_error)
