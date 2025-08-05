import logging

from app.utils.file_utils import FileInitializer
from app.utils.paths import Paths
from app.utils.defaults import base_network_config, base_profile_config, base_static_config

from app.handlers.error_handlers import handle_app_errors

logger = logging.getLogger(__name__)

class ProfileInitializer:
    """Сервис для инициализации профиля."""
    
    def __init__(self):
        pass

    @handle_app_errors(raise_on_fail=True)
    def initialize_profile(self, profile_id: str, paths: Paths) -> None:
        """Инициализировать профиль."""
        logger.info(f"Initializing profile: {profile_id}")
        
        self.create_directories(paths)
        self.create_config_files(paths)
        
        logger.info(f"Profile initialized successfully: {profile_id}")

    def create_directories(self, paths: Paths) -> None:
        """Создать необходимые директории."""
        directories = [paths.images_dir]
        
        for directory in directories:
            FileInitializer.ensure_directory(directory, raise_error=True)
            logger.debug(f"Directory ensured: {directory}")

    def create_config_files(self, paths: Paths) -> None:
        """Создать конфигурационные файлы."""
        config_files = [
            (paths.network_config_path, base_network_config(), True),
            (paths.profile_config_path, base_profile_config(), True),
            (paths.static_config_path, base_static_config(), True)
        ]
        
        for file_path, default_content, raise_error in config_files:
            FileInitializer.ensure_file_with_content(
                file_path,
                content=default_content,
                is_json=True, 
                raise_error=raise_error
            )
            logger.debug(f"Config file ensured: {file_path}")