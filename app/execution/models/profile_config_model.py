# schemas.models.profile_config_models.py

from __future__ import annotations
from pydantic import Field

from app.execution.models.base_class import JsonSerializable


class AccountReaderSettings(JsonSerializable):
    last_chapter: int = Field(default=0, ge=0, description="Last chapter read (not below 0)")
    batch_size: int = Field(default=2, ge=0, description="Batch size for processing (not below 0)")
    batch_limit: int = Field(default=100, ge=0, description="Maximum number of items to process in a batch (not below 0)")
    current_mode: str = Field(default="tokens", description="Current mode of operation, e.g., 'tokens', 'pages'")
    
    class Config:
        extra = "forbid"
        populate_by_name = True
        
