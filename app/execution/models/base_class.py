# schemas/models/base_class.py

from __future__ import annotations
from pathlib import Path
from typing import Any, Union, TypeVar, Type
from pydantic import BaseModel

from app.utils.file_utils import FileInitializer

T = TypeVar("T", bound="JsonSerializable")

class JsonSerializable(BaseModel):
    class Config:
        populate_by_name = True

    @classmethod
    def from_json(cls: Type[T], path: Union[str, Path], default: Any = None) -> T:
        data = FileInitializer.read_json(path, default=default or {})
        return cls.model_validate(data)

    def to_json(
        self,
        path: Union[str, Path],
        *,
        indent: int = 2,
        sort_keys: bool = False,
        ensure_ascii: bool = False,
        overwrite: bool = True
    ) -> None:
        FileInitializer.write_json(
            data=self.model_dump(by_alias=True),
            path=path,
            indent=indent,
            sort_keys=sort_keys,
            ensure_ascii=ensure_ascii,
            overwrite=overwrite,
        )
