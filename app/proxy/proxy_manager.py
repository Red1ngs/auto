from typing import List

from app.utils.paths import PROXY_DIR
from app.utils.file_utils import FileInitializer

from app.models.proxy_model import Proxy


class ProxyManager:
    def __init__(self):
        self.path = PROXY_DIR / "proxy.json"
        self._map = {}  # proxy_id -> Proxy
        proxies_raw = FileInitializer.read_json(self.path)

        for raw in proxies_raw:
            self._map[raw["id"]] = Proxy(**raw)

    @property
    def all(self) -> List[Proxy]:
        return list(self._map.values())

    def get(self, proxy_id: str) -> Proxy:
        return self._map.get(proxy_id)
    
proxy_manager: ProxyManager = ProxyManager()