from __future__ import annotations
from typing import Callable, Optional

from app.exceptions.base_exceptions import DataBaseException


class UserNotFoundException(DataBaseException):
    """User not found in the database."""
    
    def __init__(self, message: str = "User not found.", *, code: int = 404, on_error: Optional[Callable] = None):
        super().__init__(message, code=code, on_error=on_error)
        
        
class CardNotFoundException(DataBaseException):
    """Card not found in the database."""
    
    def __init__(self, message: str = "Card not found.", *, code: int = 404, on_error: Optional[Callable] = None):
        super().__init__(message, code=code, on_error=on_error)