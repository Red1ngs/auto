import logging

from app.utils.paths import Paths
from app.proxy.manager import proxy_manager

from .profile import Profile
from .init import ProfileInitializer  

from app.profiles.config.loader import ConfigLoader
from app.profiles.config.validator import ConfigValidator  
from app.profiles.config.service import ProfileConfigService

from app.profiles.http.service import HttpClientService
from app.profiles.proxy.service import ProxyService  

logger = logging.getLogger(__name__)


class ProfileFactory:
    """Фабрика для создания профилей с зависимостями."""
    
    def __init__(self):
        self.initializer = ProfileInitializer()

    def create_profile(self, profile_id: str) -> Profile:
        """
        Создать профиль со всеми зависимостями.
        
        Args:
            profile_id: ID профиля
            
        Returns:
            Profile: Настроенный профиль
        """
        # Создаем пути
        paths = Paths.from_profile_id(profile_id)
        
        # Инициализируем профиль
        self.initializer.initialize_profile(profile_id, paths)
        
        # Создаем сервисы
        loader = ConfigLoader()
        validator = ConfigValidator()
        config_service = ProfileConfigService(loader, validator)
        
        proxy_service = ProxyService(proxy_manager)
        http_service = HttpClientService(proxy_service, validator)
        
        # Загружаем конфигурации
        config_service.load_all_configs(paths, profile_id)
        
        # Создаем профиль
        profile = Profile(profile_id, config_service, http_service, paths)
        
        return profile