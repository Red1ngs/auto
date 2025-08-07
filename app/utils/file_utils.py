# utils.file_utils.py

from __future__ import annotations
from pathlib import Path
from typing import Any, Callable, Optional, Union
import json
import logging

logger = logging.getLogger(__name__)


class FileInitializer:
    DEFAULT_ENCODING = "utf-8"
    DEFAULT_INDENT = 2
    DEFAULT_SORT_KEYS = False
    DEFAULT_ASCII = False

    @staticmethod
    def ensure_directory(path: Union[str, Path], raise_error: bool = False, on_error: Optional[Callable] = None) -> None:
        path = Path(path)
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create directory: {path}", exc_info=True)
                if raise_error:
                    raise FileNotFoundError(f"Directory {path} could not be created.", on_error=on_error) from e

    @staticmethod
    def ensure_file_with_content(
        path: Union[str, Path],
        content: str | dict | list = "",
        is_json: bool = False,
        raise_error: bool = False,
        on_error: Optional[Callable] = None
    ) -> None:
        path = Path(path)
        if not path.exists():
            try:
                FileInitializer.ensure_directory(path.parent)

                if is_json:
                    with path.open("w", encoding=FileInitializer.DEFAULT_ENCODING) as f:
                        json.dump(
                            content or {},
                            f,
                            indent=FileInitializer.DEFAULT_INDENT,
                            ensure_ascii=FileInitializer.DEFAULT_ASCII,
                            sort_keys=FileInitializer.DEFAULT_SORT_KEYS
                        )
                else:
                    path.write_text(str(content), encoding=FileInitializer.DEFAULT_ENCODING)
            except Exception as e:
                logger.error(f"Failed to create file: {path}", exc_info=True)
                if raise_error:
                    raise FileNotFoundError(f"File {path} could not be created.", on_error=on_error) from e

    @staticmethod
    def delete_file(path: Union[str, Path]) -> None:
        path = Path(path)
        try:
            if path.exists():
                path.unlink()
        except Exception:
            logger.warning(f"Could not delete file: {path}", exc_info=True)

    @staticmethod
    def read_json(path: Union[str, Path], default: Any = None) -> Any:
        path = Path(path)
        if not path.exists():
            return default if default is not None else {}

        with path.open("r", encoding=FileInitializer.DEFAULT_ENCODING) as f:
            return json.load(f)

    @staticmethod
    def write_json(
        data: Any,
        path: Union[str, Path],
        *,
        indent: int = DEFAULT_INDENT,
        sort_keys: bool = DEFAULT_SORT_KEYS,
        ensure_ascii: bool = DEFAULT_ASCII,
        overwrite: bool = True
    ) -> None:
        path = Path(path)
        if not overwrite and path.exists():
            raise FileExistsError(f"Файл уже существует: {path}")

        FileInitializer.ensure_directory(path.parent)

        with path.open("w", encoding=FileInitializer.DEFAULT_ENCODING) as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)
