from __future__ import annotations
from pydantic import BaseModel, Field, RootModel
from typing import List, Literal, Dict

from app.utils.defaults import base_cookie, base_headers
from app.models.base_class import JsonSerializable

class AccountReaderSettings(JsonSerializable):
    last_chapter: int = Field(default=0, ge=0, description="Last chapter read (not below 0)")
    batch_size: int = Field(default=2, ge=0, description="Batch size for processing (not below 0)")
    batch_limit: int = Field(default=100, ge=0, description="Maximum number of items to process in a batch (not below 0)")
    current_mode: str = Field(default="tokens", description="Current mode of operation, e.g., 'tokens', 'pages'")
    
    class Config:
        extra = "forbid"
        populate_by_name = True

class Hallmark(BaseModel):
    key: str
    value: str | None = None

class Mode(BaseModel):
    match: Literal["OR", "AND"]
    request_delay: int
    hallmarks: List[Hallmark]
    how_many: int

class ReaderModes(RootModel[Dict[str, Mode]]):

    def __getitem__(self, item: str) -> Mode:
        return self.root[item]

    def keys(self):
        return self.root.keys()

    def items(self):
        return self.root.items()

    def values(self):
        return self.root.values()

class Reader(BaseModel):
    modes: ReaderModes

class StaticConfig(JsonSerializable):
    reader: Reader
        
        
class Headers(BaseModel):
    """HTTP-Headers Model"""
    Host: str
    UserAgent: str = Field(alias="User-Agent")
    Accept: str
    AcceptLanguage: str = Field(alias="Accept-Language")
    AcceptEncoding: str = Field(alias="Accept-Encoding")
    Connection: str
    SecFetchDest: str = Field(alias="Sec-Fetch-Dest")
    SecFetchMode: str = Field(alias="Sec-Fetch-Mode")
    SecFetchSite: str = Field(alias="Sec-Fetch-Site")
    SecFetchUser: str = Field(alias="Sec-Fetch-User")
    Priority: str
    x_csrf_token: str = Field(alias="x-csrf-token")
    x_requested_with: str = Field(alias="x-requested-with")

    class Config:
        extra = "forbid"
        populate_by_name = True


class Cookie(BaseModel):
    """Cookie Model"""
    XSRF_TOKEN: str = Field(alias="XSRF-TOKEN")
    mangabuff_session: str
    ddg9: str = Field(alias="__ddg9_")
    theme: str

    class Config:
        extra = "forbid"
        populate_by_name = True


class AccountHTTPData(JsonSerializable):
    cookie: Cookie
    headers: Headers
    proxy: str | None = None
    base_url: str
    data_time: int
    retries: int = 3
    timeout: int = 10

    class Config:
        extra = "allow"
        populate_by_name = True

    def is_default(self) -> bool:
        return (
            self.cookie.model_dump(by_alias=True) == base_cookie() and
            self.headers.model_dump(by_alias=True) == base_headers()
        )