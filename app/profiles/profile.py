from app.profiles.http_client import HttpClient
from app.profiles.config_service import ProfileConfigService
from app.profiles.http_service import HttpClientService
from app.utils.paths import Paths
from typing import Dict, Any, Optional

class Profile:
    """
    Упрощенный класс профиля - координатор сервисов.
    
    Attributes:
        profile_id: Уникальный идентификатор профиля
        paths: Пути к файлам и директориям профиля
        config_service: Сервис конфигураций
        http_service: HTTP сервис
    """
    
    def __init__(self, 
                 profile_id: str,
                 config_service: ProfileConfigService,
                 http_service: HttpClientService,
                 paths: Paths):
        self.profile_id = profile_id
        self.paths = paths
        self.config_service = config_service
        self.http_service = http_service

    def get_client(self, use_account: bool = True) -> HttpClient:
        """Получить HTTP-клиент."""
        http_data = self.config_service.get_config('network')
        return self.http_service.get_or_create_client(http_data, use_account, self.profile_id)

    def set_proxy(self, proxy_id: Optional[str]) -> bool:
        """Установить прокси."""
        result = self.http_service.proxy_service.configure_proxy(proxy_id, self.profile_id)
        self.http_service.update_proxy(self.profile_id)
        return result

    def reload_profile_settings(self) -> bool:
        """Перезагрузить настройки профиля."""
        return self.config_service.reload_config('profile_settings', self.paths)

    def debug_headers_and_cookies(self) -> Dict[str, Any]:
        """Получить отладочную информацию."""
        return self.http_service.get_debug_info()

    @property
    def is_initialized(self) -> bool:
        """Проверить инициализацию профиля."""
        return self.config_service.is_profile_ready()

    def __str__(self) -> str:
        return f"Profile(profile_id='{self.profile_id}')"

    def __repr__(self) -> str:
        return f"Profile(profile_id='{self.profile_id}', account_dir='{self.paths.account_dir}')"
