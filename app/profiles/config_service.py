import logging
from typing import Optional, Dict, Any

from app.utils.paths import Paths

from app.profiles.config_loader import ConfigLoader
from app.profiles.config_validator import ConfigValidator

logger = logging.getLogger(__name__)

class ProfileConfigService:
    """Сервис для управления конфигурациями профиля."""
    
    def __init__(self, loader: ConfigLoader, validator: ConfigValidator):
        self.loader = loader
        self.validator = validator
        self._configs: Dict[str, Any] = {}

    def load_all_configs(self, paths: Paths, profile_id: str) -> Dict[str, Any]:
        """Загрузить все конфигурации профиля."""
        logger.info(f"Loading all configs for profile: {profile_id}")
        
        # Загружаем конфигурации
        network_config = self.loader.load_network_config(paths)
        profile_settings = self.loader.load_profile_settings(paths)
        static_config = self.loader.load_static_config(paths)
        
        # Валидируем критичные конфигурации
        self.validator.validate_profile_settings(profile_settings, profile_id)
        self.validator.validate_static_config(static_config)
        
        # Сохраняем в кеше
        self._configs = {
            'network': network_config,
            'profile_settings': profile_settings,
            'static': static_config
        }
        
        logger.info(f"All configs loaded for profile: {profile_id}")
        return self._configs

    def reload_config(self, config_type: str, paths: Paths) -> bool:
        """Перезагрузить конкретную конфигурацию."""
        try:
            if config_type == 'profile_settings':
                config = self.loader.load_profile_settings(paths)
            elif config_type == 'network':
                config = self.loader.load_network_config(paths)
            elif config_type == 'static':
                config = self.loader.load_static_config(paths)
            else:
                logger.error(f"Unknown config type: {config_type}")
                return False
                
            self._configs[config_type] = config
            logger.info(f"Config '{config_type}' reloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload config '{config_type}': {e}")
            return False

    def get_config(self, config_type: str) -> Optional[Any]:
        """Получить конфигурацию по типу."""
        return self._configs.get(config_type)

    def is_profile_ready(self) -> bool:
        """Проверить готовность профиля."""
        return self.validator.is_config_complete(self._configs)