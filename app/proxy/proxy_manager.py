
from typing import List, Optional, Dict
import logging

from app.utils.paths import PROXY_DIR
from app.utils.file_utils import FileInitializer

from app.models.proxy_model import Proxy

logger = logging.getLogger(__name__)

class ProxyManager:
    """Менеджер для управління проксі-серверами."""
    
    def __init__(self):
        self.path = PROXY_DIR / "proxy.json"
        self._map: Dict[str, Proxy] = {}
        self._load_proxies()

    def _load_proxies(self) -> None:
        """Завантажує проксі з JSON файлу."""
        try:
            proxies_raw = FileInitializer.read_json(self.path)
            for raw in proxies_raw:
                proxy = Proxy(**raw)
                self._map[proxy.id] = proxy
                logger.debug(f"Loaded proxy: {proxy}")
            logger.info(f"Loaded {len(self._map)} proxies")
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")
            self._map["0"] = Proxy(id="0")

    @property
    def all(self) -> List[Proxy]:
        """Повертає всі доступні проксі."""
        return list(self._map.values())
    
    @property
    def all_proxy_ids(self) -> List[str]:
        return [str(p.id) for p in self.all]
    
    @property
    def valid_proxies(self) -> List[Proxy]:
        """Повертає тільки валідні проксі (не за замовчуванням)."""
        return [proxy for proxy in self._map.values() if not proxy.is_default]

    def get(self, proxy_id: str) -> Optional[Proxy]:
        """
        Отримує проксі за ID.
        
        Args:
            proxy_id: ID проксі
            
        Returns:
            Proxy або None якщо не знайдено
        """
        return self._map.get(proxy_id)
    
    def reload(self) -> bool:
        """
        Перезавантажує проксі з файлу.
        
        Returns:
            True якщо успішно, False якщо помилка
        """
        try:
            self._map.clear()
            self._load_proxies()
            return True
        except Exception as e:
            logger.error(f"Failed to reload proxies: {e}")
            return False
        

# Глобальний екземпляр менеджера проксі
proxy_manager: ProxyManager = ProxyManager()