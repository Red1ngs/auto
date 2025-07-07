from pathlib import Path
import json
from typing import Any, Callable, Optional

from exceptions.exceptions import (
    ProfileDirNotFoundError, ProfileNetworkConfigNotFoundError, AppError
    )

class FileInitializer:
    @staticmethod
    def ensure_directory(path: Path, raise_error: bool = False, on_error: Optional[Callable] = None) -> None:
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                if raise_error:
                    raise ProfileDirNotFoundError(
                        f"Directory {path} could not be created.",
                        on_error=on_error
                    ) from e

    @staticmethod
    def ensure_json_file(
        path: Path,
        default_data: Any = {},
        raise_error: bool = False,
        on_error: Optional[Callable] = None
    ) -> None:
        if not path.exists():
            try:
                FileInitializer.ensure_directory(path.parent)
                with path.open("w", encoding="utf-8") as f:
                    json.dump(default_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                if raise_error:
                    raise ProfileNetworkConfigNotFoundError(
                        f"JSON file {path} could not be created.",
                        on_error=on_error
                    ) from e

    @staticmethod
    def ensure_file(
        path: Path,
        content: str = "",
        raise_error: bool = False,
        on_error: Optional[Callable] = None
    ) -> None:
        if not path.exists():
            try:
                FileInitializer.ensure_directory(path.parent)
                path.write_text(content, encoding="utf-8")
            except Exception as e:
                if raise_error:
                    raise AppError(
                        f"File {path} could not be created.",
                        on_error=on_error
                    ) from e
