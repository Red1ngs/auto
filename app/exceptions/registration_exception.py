from __future__ import annotations
from typing import Callable, Optional

from app.exceptions.base_exceptions import ProfileRegistrationException


class ProfileNetworkConfigNotFoundException(ProfileRegistrationException):
    """Network config not found."""

    def __init__(self, message: str = "Network config not found.", *, code: int = 404, on_error: Optional[Callable] = None):
        super().__init__(message, code=code, on_error=on_error)
        

class ProfileNetworkConfigEmptyException(ProfileRegistrationException):
    """Network config empty."""

    def __init__(self, message: str = "Network config empty.", *, code: int = 404, on_error: Optional[Callable] = None):
        super().__init__(message, code=code, on_error=on_error)
  

class ProfileReaderConfigNotFoundException(ProfileRegistrationException):
    """Reader config not found."""

    def __init__(self, message: str = "Reader config not found.", *, code: int = 404, on_error: Optional[Callable] = None):
        super().__init__(message, code=code, on_error=on_error)