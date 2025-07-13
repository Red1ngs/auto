from pydantic import BaseModel
from typing import List, Literal

from app.schemas.models.base_class import JsonSerializable

class Hallmark(BaseModel):
    key: str
    value: str | None = None

class Mode(BaseModel):
    match: Literal["OR", "AND"]
    request_delay: int
    hallmarks: List[Hallmark]
    how_many: int

class ReaderModes(BaseModel):
    tokens: Mode
    cards: Mode

class Reader(BaseModel):
    modes: ReaderModes

class AppConfig(JsonSerializable):
    app_name: str
    version: str
    description: str
    reader: Reader
