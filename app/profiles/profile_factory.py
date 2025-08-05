import logging

from app.utils.paths import Paths
from app.proxy.proxy_manager import proxy_manager

from app.profiles.config_loader import ConfigLoader
from app.profiles.config_validator import ConfigValidator
from app.profiles.profile_init import ProfileInitializer    
from app.profiles.profile import Profile 
from app.profiles.config_service import ProfileConfigService
from app.profiles.http_service import HttpClientService
from app.profiles.proxy_service import ProxyService  

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