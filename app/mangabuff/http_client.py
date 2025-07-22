import logging
import json
import aiohttp

from typing import Dict, Optional

from app.models.profile_models import AccountHTTPData

from app.handlers.http_handlers import log_http_request

logger = logging.getLogger(__name__)

class HttpClient:
    def __init__(self, http_data: Optional[AccountHTTPData], *, use_account: bool = True):
        self.headers = http_data.headers.model_dump() if use_account else {}
        self.cookie = http_data.cookie.model_dump() if use_account else {}
        self.session: Optional[aiohttp.ClientSession] = None

    async def init_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=self.headers, cookies=self.cookie)

    @log_http_request("POST")
    async def post(self, url: str, payload: Dict, *, retries=3, timeout=1360.0) -> Optional[aiohttp.ClientResponse]:
        if self.session is None or self.session.closed:
            await self.init_session()
        return await self.session.post(url, data=json.dumps(payload), timeout=timeout)

    @log_http_request("GET")
    async def get(self, url: str, payload=None, *, retries=3, timeout=360.0) -> Optional[aiohttp.ClientResponse]:
        if self.session is None or self.session.closed:
            await self.init_session()
        return await self.session.get(url, params=payload, timeout=timeout)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
