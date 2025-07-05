from pydantic import BaseModel, Field

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
    remember_web_: str
    XSRF_TOKEN: str = Field(alias="XSRF-TOKEN")
    mangabuff_session: str
    ddg9: str = Field(alias="__ddg9_")
    theme: str
    
    class Config:
        extra = "forbid"
        populate_by_name = True  

class Account_http_data(BaseModel):
    cookie: Cookie
    headers: Headers

    class Config:
        extra = "allow"
        populate_by_name = True  