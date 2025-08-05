import logging
from typing import Optional

from app.models.proxy_model import Proxy

logger = logging.getLogger(__name__)

class ProxyService:
    """Сервис для управления прокси."""
    
    def __init__(self, proxy_manager):
        self.proxy_manager = proxy_manager
        self.current_proxy: Optional[Proxy] = None

    def configure_proxy(self, proxy_id: Optional[str], profile_id: str) -> bool:
        """
        Настроить прокси для профиля.
        
        Args:
            proxy_id: ID прокси или None для использования по умолчанию
            profile_id: ID профиля для логирования
            
        Returns:
            bool: True если прокси установлен успешно
        """
        if not proxy_id:
            self.current_proxy = self.proxy_manager.get_default()
            logger.info(f"Set default proxy for profile {profile_id}")
            return True

        proxy = self.proxy_manager.get(proxy_id)
        
        if not proxy:
            logger.warning(f"Proxy with ID '{proxy_id}' not found for profile {profile_id}")
            self.current_proxy = self.proxy_manager.get_default()
            return False

        self.current_proxy = proxy
        
        if proxy.is_default:
            logger.info(f"Set default proxy for profile {profile_id}")
        else:
            logger.info(f"Set proxy {proxy} for profile {profile_id}")
        
        return True

    def get_current_proxy(self) -> Optional[Proxy]:
        """Получить текущий прокси."""
        return self.current_proxy

    def reset_to_default(self) -> None:
        """Сбросить прокси к значению по умолчанию."""
        self.current_proxy = self.proxy_manager.get_default()