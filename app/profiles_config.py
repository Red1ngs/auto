import logging
from typing import Optional

from app.execution.models.app_config_model import AppConfig
from app.exceptions.path_exceptions import AppConfigMissingException
from app.handlers.error_handlers import async_handle_app_errors
from app.utils.paths import PROJECT_ROOT
from app.utils.file_utils import FileInitializer

logger = logging.getLogger(__name__)

class AppConfigManager:
    async def __init__(self):
        """Ініціалізація менеджера конфігурації додатку"""
        self.app_config_path = PROJECT_ROOT / "profiles_config.json"

    @async_handle_app_errors(raise_on_fail=True)
    async def load_app_config(self) -> Optional[AppConfig]:
        """Завантажити налаштування профілю"""
        await FileInitializer.ensure_file_with_content(
            self.app_config_path,
            is_json=True,
            raise_error=True,
            on_error=self._handle_missing_app_config
        )

        reader_setting = await AppConfig.from_json(self.app_config_path)
        logger.debug("App config loaded")
        return reader_setting

    def _handle_missing_app_config(self):
        error_msg = "App config is missing. Please ensure the profiles_config.json file exists in the app directory."
        logger.error(error_msg)
        raise AppConfigMissingException(message=error_msg)

app_config = AppConfigManager()

