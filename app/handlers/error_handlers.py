# handlers/decorators.py
import logging
from typing import Callable, TypeVar, ParamSpec, cast
import functools

from app.exceptions.exceptions import AppError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

P = ParamSpec("P")
R = TypeVar("R")

_logged_errors = set()


def handle_app_errors(raise_on_fail: bool = False):
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except AppError as e:
                error_key = (str(e), getattr(e, "code", None))
                if error_key not in _logged_errors:
                    logger.error(f"[{e.__class__.__name__}] {e} (code={e.code})")
                    _logged_errors.add(error_key)

                if e.on_error:
                    try:
                        return e.on_error()
                    except Exception as inner:
                        logger.exception(f"[on_error failed] {inner}")

                if raise_on_fail:
                    raise
            except Exception as ex:
                logger.exception(f"Unexpected error in {func.__name__}: {ex}")
                raise
        return cast(Callable[P, R], wrapper)
    return decorator

