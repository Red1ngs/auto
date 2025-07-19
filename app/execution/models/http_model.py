# schemas.models.http_model.py

from __future__ import annotations
from pydantic import BaseModel, Field

from app.utils.defaults import base_cookie, base_headers
from app.execution.models.base_class import JsonSerializable

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
