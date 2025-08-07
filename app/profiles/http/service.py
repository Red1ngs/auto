import logging
from typing import Optional, Dict, Any

from .client import HttpClient
from app.models.profile_models import AccountHTTPData

from app.profiles.proxy.service import ProxyService
from app.profiles.config.validator import ConfigValidator

logger = logging.getLogger(__name__)

class HttpClientService:
    """Сервис для управления HTTP-клиентом."""
    
    def __init__(self, proxy_service: ProxyService, validator: ConfigValidator):
        self.proxy_service = proxy_service
        self.validator = validator
        self._client: Optional[HttpClient] = None

    def create_client(self, http_data: Optional[AccountHTTPData], use_account: bool, profile_id: str) -> HttpClient:
        """
        Создать HTTP-клиент.
        
        Args:
            http_data: HTTP данные аккаунта
            use_account: Использовать ли данные аккаунта
            profile_id: ID профиля для логирования
            
        Returns:
            HttpClient: Настроенный HTTP-клиент
        """
        if use_account:
            self.validator.validate_network_config(http_data, profile_id)

        client = HttpClient(http_data, use_account=use_account)
        
        # Применяем прокси если есть
        current_proxy = self.proxy_service.get_current_proxy()
        if current_proxy and not current_proxy.is_default:
            client.set_proxy(current_proxy.as_dict)
            logger.info(f"Applied proxy {current_proxy} to HTTP client for profile {profile_id}")
        
        return client

    def get_or_create_client(self, http_data: Optional[AccountHTTPData], use_account: bool, profile_id: str) -> HttpClient:
        """Получить существующий или создать новый HTTP-клиент."""
        if self._client is None:
            self._client = self.create_client(http_data, use_account, profile_id)
        return self._client

    async def close_client(self) -> None:
        """Закрыть HTTP-клиент."""
        if self._client:
            await self._client.close()
            self._client = None

    def get_debug_info(self) -> Dict[str, Any]:
        """Получить отладочную информацию о клиенте."""
        if not self._client:
            return {"status": "No client initialized"}
            
        return {
            "headers_count": len(self._client.headers),
            "cookies_count": len(self._client.cookie),
            "has_proxy": bool(self._client.proxy),
            "proxy_url": self._client.proxy if self._client.proxy else None,
            "headers_sample": dict(list(self._client.headers.items())[:3]) if self._client.headers else {},
            "cookies_sample": dict(list(self._client.cookie.items())[:3]) if self._client.cookie else {}
        }

    def update_proxy(self, profile_id: str) -> None:
        """Обновить прокси для существующего клиента."""
        if self._client:
            current_proxy = self.proxy_service.get_current_proxy()
            if current_proxy and current_proxy.is_default:
                self._client.set_proxy({})
            elif current_proxy:
                self._client.set_proxy(current_proxy.as_dict)
            logger.debug(f"Updated proxy for existing client, profile {profile_id}")
