import logging
from typing import Optional, Dict, Any

from app.models.profile_models import AccountHTTPData, AccountReaderSettings, StaticConfig

from app.exceptions.registration_exception import ProfileNetworkConfigEmptyException, ProfileReaderConfigNotFoundException
from app.exceptions.path_exceptions import StaticConfigMissingException

logger = logging.getLogger(__name__)

class ConfigValidator:
    """Валидация конфигураций."""
    
    def validate_network_config(self, config: Optional[AccountHTTPData], profile_id: str) -> None:
        """Валидация сетевой конфигурации."""
        if not config or config.is_default():
            error_msg = (
                f"Network configuration for profile '{profile_id}' is empty. "
                "Cannot proceed with account-based HTTP client."
            )
            logger.error(error_msg)
            raise ProfileNetworkConfigEmptyException(error_msg)
    
    def validate_profile_settings(self, config: Optional[AccountReaderSettings], profile_id: str) -> None:
        """Валидация настроек профиля."""
        if not config:
            error_msg = (
                f"Reader configuration for profile '{profile_id}' is empty. "
                "Cannot create profile."
            )
            logger.error(error_msg)
            raise ProfileReaderConfigNotFoundException(error_msg)
    
    def validate_static_config(self, config: Optional[StaticConfig]) -> None:
        """Валидация статической конфигурации."""
        if not config:
            error_msg = "App config is missing. Please ensure the static_config.json file exists in the app directory."
            logger.error(error_msg)
            raise StaticConfigMissingException(message=error_msg)

    def is_config_complete(self, configs: Dict[str, Any]) -> bool:
        """Проверить полноту всех конфигураций."""
        required_configs = ['network', 'profile_settings', 'static']
        return all(configs.get(key) is not None for key in required_configs)