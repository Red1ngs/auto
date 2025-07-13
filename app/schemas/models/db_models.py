# app/schemas/models/db_models.py
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


class User(BaseModel):
    user_id: str = Field(..., pattern=r"^\d+$", description="ID пользователя (в строке)")
    username: Optional[str] = None
    image: Optional[str] = None
    category: Optional[str] = None
    lock: Optional[Literal[0, 1]] = Field(default=0)

    @field_validator('username', 'image', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        return v or None
    
    class Config:
        extra = "forbid"