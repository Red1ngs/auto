import json
import logging
import aiohttp

from app.handlers.decorators import log_http_request
from app.models.profile_models import AccountHTTPData
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class HttpClient:
    """HTTP клиент с поддержкой прокси."""
    
    def __init__(self, http_data: Optional[AccountHTTPData], *, use_account: bool = True):
        # Очищаем заголовки от None ключей и значений
        raw_headers = http_data.headers.model_dump(by_alias=True) if (use_account and http_data) else {}
        self.headers = self._clean_headers(raw_headers)
        
        # Очищаем cookies от None ключей и значений
        raw_cookies = http_data.cookie.model_dump(by_alias=True) if (use_account and http_data) else {}
        self.cookie = self._clean_cookies(raw_cookies)
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.proxy: Optional[str] = None  # URL типа "http://user:pass@ip:port"

    def _clean_headers(self, headers: Dict) -> Dict[str, str]:
        """Очищает заголовки от None ключей и значений."""
        if not headers:
            return {}
            
        cleaned = {}
        for key, value in headers.items():
            if key is None or value is None:
                logger.warning(f"Skipping invalid header: key={key}, value={value}")
                continue
                
            str_key = str(key).strip()
            str_value = str(value).strip()
            
            if not str_key:
                logger.warning(f"Skipping empty header key: value={str_value}")
                continue
                
            cleaned[str_key] = str_value
            
        return cleaned
    
    def _clean_cookies(self, cookies: Dict) -> Dict[str, str]:
        """Очищает cookies от None ключей и значений."""
        if not cookies:
            return {}
            
        cleaned = {}
        for key, value in cookies.items():
            if key is None or value is None:
                logger.warning(f"Skipping invalid cookie: key={key}, value={value}")
                continue
                
            str_key = str(key).strip()
            str_value = str(value).strip()
            
            if not str_key:
                logger.warning(f"Skipping empty cookie key: value={str_value}")
                continue
                
            cleaned[str_key] = str_value
            
        return cleaned
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> aiohttp.ClientResponse:
        """Проверяет статус ответа и вызывает исключения при ошибках."""
        if response.status == 429:
            raise Exception("Rate limit exceeded")
        
        if response.status != 200:
            try:
                result = await response.json()
                message = result.get("message", f"Unexpected status code: {response.status}")
            except Exception:
                message = f"Unexpected status code: {response.status}"
            raise Exception(message)
        
        return response

    def set_proxy(self, proxy_dict: Optional[Dict[str, str]]) -> None:
        """Устанавливает прокси для HTTP клиента."""
        if proxy_dict:
            self.proxy = proxy_dict.get("https") or proxy_dict.get("http")
            if self.proxy:
                logger.debug(f"Proxy set: {self.proxy}")
        else:
            self.proxy = None
            logger.debug("Proxy cleared")

    async def init_session(self):
        """Инициализирует HTTP сессию."""
        if self.session is None or self.session.closed:
            safe_headers = self._clean_headers(self.headers)
            safe_cookies = self._clean_cookies(self.cookie)
            
            self.session = aiohttp.ClientSession(
                headers=safe_headers, 
                cookies=safe_cookies
            )
            logger.debug(f"HTTP session initialized with {len(safe_headers)} headers and {len(safe_cookies)} cookies")

    @log_http_request("POST")
    async def post(self, url: str, payload: Dict, *, retries=3, timeout=1360.0) -> Optional[aiohttp.ClientResponse]:
        if self.session is None or self.session.closed:
            await self.init_session()

        post_headers = self._clean_headers(dict(self.headers))
        post_headers.setdefault("Content-Type", "application/json")

        logger.debug(f"POST request to {url} {'with proxy' if self.proxy else 'without proxy'}")

        try:
            response = await self.session.post(
                url,
                data=json.dumps(payload),
                headers=post_headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
                proxy=self.proxy
            )
            return await self._handle_response(response)
        except Exception as e:
            logger.error(f"POST request failed: {e}")
            raise

    @log_http_request("GET")
    async def get(self, url: str, payload=None, *, retries=3, timeout=360.0) -> Optional[aiohttp.ClientResponse]:
        if self.session is None or self.session.closed:
            await self.init_session()

        logger.debug(f"GET request to {url} {'with proxy' if self.proxy else 'without proxy'}")

        try:
            response = await self.session.get(
                url,
                params=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
                proxy=self.proxy
            )
            return await self._handle_response(response)
        except Exception as e:
            logger.error(f"GET request failed: {e}")
            raise

    async def close(self):
        """Закрывает HTTP сессию."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("HTTP session closed")