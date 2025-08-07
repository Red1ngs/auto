import logging
from typing import Dict

from app.clients.proxy.client import proxy_manager
from app.utils.paths import Paths

from .init import ProfileInitializer
from .profile import Profile

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

class ProfileManager:
    """
    Менеджер профилей с упрощенной архитектурой.
    
    Attributes:
        _profiles_cache: Внутренний кеш профилей
        _factory: Фабрика профилей
    """
    
    def __init__(self):
        self._profiles_cache: Dict[str, Profile] = {}
        self._factory = ProfileFactory()
        logger.info("ProfileManager initialized")

    def get_profile(self, profile_id: str, use_cache: bool = True) -> Profile:
        """
        Получить профиль по profile_id.
        
        Args:
            profile_id: Уникальный идентификатор профиля
            use_cache: Использовать кеширование
            
        Returns:
            Profile: Профиль пользователя
            
        Raises:
            AppError: При ошибке создания или загрузки профиля
        """
        if use_cache and profile_id in self._profiles_cache:
            logger.debug(f"Returning cached profile for: {profile_id}")
            return self._profiles_cache[profile_id]

        try:
            profile = self._factory.create_profile(profile_id)
            
            if use_cache:
                self._profiles_cache[profile_id] = profile
                logger.debug(f"Profile cached for: {profile_id}")
            
            return profile
            
        except Exception as e:
            logger.error(f"Failed to get profile {profile_id}: {e}")
            raise

    def remove_from_cache(self, profile_id: str) -> bool:
        """Удалить профиль из кеша."""
        if profile_id in self._profiles_cache:
            del self._profiles_cache[profile_id]
            logger.debug(f"Profile removed from cache: {profile_id}")
            return True
        return False

    def clear_cache(self) -> None:
        """Очистить кеш профилей."""
        self._profiles_cache.clear()
        logger.debug("Profile cache cleared")

    def get_cached_profiles_count(self) -> int:
        """Получить количество кешированных профилей."""
        return len(self._profiles_cache)


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

# Глобальный экземпляр менеджера профилей
profile_manager: ProfileManager = ProfileManager()