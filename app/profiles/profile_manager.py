import logging
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from app.schemas.models.http_model import AccountHTTPData
from app.exceptions.exceptions import (
    AppError, ProfileNetworkConfigEmptyError
)
from app.utils.paths import ACCOUNTS_DIR
from app.utils.file_utils import FileInitializer
from app.utils.defaults import base_network_config
from app.handlers.error_handlers import handle_app_errors
from app.mangabuff.http_client import HttpClient

logger = logging.getLogger(__name__)


@dataclass
class ProfilePaths:
    """Централізовані шляхи профілю для кращого управління"""
    profile_dir: Path
    reader_dir: Path
    cards_images_dir: Path
    network_config_path: Path
    reader_config_path: Path
    reader_stats_path: Path
    avatar_path: Path

    @classmethod
    def from_user_id(cls, user_id: str) -> "ProfilePaths":
        """Створити ProfilePaths з user_id"""
        profile_dir = ACCOUNTS_DIR / user_id
        reader_dir = profile_dir / "reader"
        
        return cls(
            profile_dir=profile_dir,
            reader_dir=reader_dir,
            cards_images_dir=reader_dir / "cards_images",
            network_config_path=profile_dir / "network_config.json",
            reader_config_path=reader_dir / "reader_config.json",
            reader_stats_path=reader_dir / "reader_stats.json",
            avatar_path=profile_dir / "avatar.png"
        )


class Profile:
    """Основний клас профілю користувача"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.paths = ProfilePaths.from_user_id(user_id)
        self._initialize_profile()
        self.storage = ProfileStorage(self)
        self.http = ProfileHTTP(self)

    @handle_app_errors(raise_on_fail=True)
    def _initialize_profile(self) -> None:
        """Ініціалізація профілю та створення необхідних директорій і файлів"""
        logger.info(f"Initializing profile for user: {self.user_id}")
        
        # Створення директорій
        self._create_directories()
        
        # Створення конфігураційних файлів
        self._create_config_files()
        
        logger.info(f"Profile initialized successfully for user: {self.user_id}")

    def _create_directories(self) -> None:
        """Створення необхідних директорій"""
        directories = [
            self.paths.profile_dir,
            self.paths.reader_dir,
            self.paths.cards_images_dir
        ]
        
        for directory in directories:
            FileInitializer.ensure_directory(directory, raise_error=True)
            logger.debug(f"Directory ensured: {directory}")

    def _create_config_files(self) -> None:
        """Створення конфігураційних файлів"""
        config_files = [
            (self.paths.network_config_path, base_network_config()),
            (self.paths.reader_config_path, self._get_default_reader_config()),
            (self.paths.reader_stats_path, {})
        ]
        
        for file_path, content in config_files:
            FileInitializer.ensure_file_with_content(
                file_path,
                content=content,
                raise_error=True,
                is_json=True
            )
            logger.debug(f"Config file ensured: {file_path}")

    @staticmethod
    def _get_default_reader_config() -> Dict[str, Any]:
        """Отримати конфігурацію читача за замовчуванням"""
        return {
            "batch_size": 2,
            "batch_limit": 100,
            "current_mode": "tokens"
        }

    def __str__(self) -> str:
        return f"Profile(user_id='{self.user_id}')"

    def __repr__(self) -> str:
        return f"Profile(user_id='{self.user_id}', profile_dir='{self.paths.profile_dir}')"


class ProfileStorage:
    """Клас для управління зберіганням даних профілю"""
    
    def __init__(self, profile: Profile):
        self.profile = profile
        self._initialize_storage()

    @handle_app_errors(raise_on_fail=True)
    def _initialize_storage(self) -> None:
        """Ініціалізація сховища профілю"""
        logger.info(f"Initializing storage for profile: {self.profile.user_id}")
        
        self.http_data = self._load_http_data()
        self.profile_settings = self._load_profile_settings()
        self.profile_stats = self._load_profile_stats()
        
        logger.info(f"Storage initialized for profile: {self.profile.user_id}")

    @handle_app_errors(raise_on_fail=False)
    def _load_profile_settings(self) -> Optional[Dict[str, Any]]:
        """Завантажити налаштування профілю"""
        # TODO: Реалізувати завантаження налаштувань
        logger.debug("Profile settings loading not implemented yet")
        return None

    @handle_app_errors(raise_on_fail=False)
    def _load_profile_stats(self) -> Optional[Dict[str, Any]]:
        """Завантажити статистику профілю"""
        # TODO: Реалізувати завантаження статистики
        logger.debug("Profile stats loading not implemented yet")
        return None

    @handle_app_errors(raise_on_fail=False)
    def _load_http_data(self) -> Optional[AccountHTTPData]:
        """Завантажити HTTP-дані профілю"""
        try:
            FileInitializer.ensure_file_with_content(
                self.profile.paths.network_config_path,
                content=base_network_config(),
                is_json=True,
                raise_error=True,
                on_error=self._handle_missing_network_config
            )
            
            http_data = AccountHTTPData.from_json(self.profile.paths.network_config_path)
            logger.debug(f"HTTP data loaded for profile: {self.profile.user_id}")
            return http_data
            
        except Exception as e:
            logger.error(f"Failed to load HTTP data for profile {self.profile.user_id}: {e}")
            return None

    def _handle_missing_network_config(self) -> None:
        """Обробник відсутнього мережевого конфігу"""
        error_msg = (
            f"Network configuration for profile '{self.profile.user_id}' is empty. "
            "Cannot proceed with account-based HTTP client."
        )
        logger.error(error_msg)
        raise ProfileNetworkConfigEmptyError(error_msg)

    def reload_http_data(self) -> bool:
        """Перезавантажити HTTP-дані"""
        try:
            self.http_data = self._load_http_data()
            return self.http_data is not None
        except Exception as e:
            logger.error(f"Failed to reload HTTP data: {e}")
            return False


class ProfileHTTP:
    """Клас для управління HTTP-клієнтом профілю"""
    
    def __init__(self, profile: Profile):
        self.profile = profile
        self.storage = profile.storage

    @handle_app_errors(raise_on_fail=True)
    def get_client(self, use_account: bool = True) -> HttpClient:
        """Отримати HTTP-клієнт для профілю"""
        if use_account:
            if not self._is_account_data_valid():
                error_msg = (
                    f"Network configuration for profile '{self.profile.user_id}' "
                    "is missing or default."
                )
                logger.error(error_msg)
                raise ProfileNetworkConfigEmptyError(error_msg)
            
            http_data = self.storage.http_data
            logger.debug(f"Creating HTTP client with account data for: {self.profile.user_id}")
        else:
            http_data = None
            logger.debug(f"Creating HTTP client without account data for: {self.profile.user_id}")

        return HttpClient(http_data, use_account=use_account)

    def _is_account_data_valid(self) -> bool:
        """Перевірити чи валідні дані акаунта"""
        return (
            self.storage.http_data is not None and 
            not self.storage.http_data.is_default()
        )

    def refresh_account_data(self) -> bool:
        """Оновити дані акаунта"""
        return self.storage.reload_http_data()


class ProfileManager:
    """Менеджер профілів для управління множинними профілями"""
    
    def __init__(self):
        self._profiles_cache: Dict[str, Profile] = {}
        logger.info("ProfileManager initialized")

    def get_profile(self, user_id: str, use_cache: bool = True) -> Profile:
        """Отримати профіль за user_id"""
        if use_cache and user_id in self._profiles_cache:
            logger.debug(f"Returning cached profile for user: {user_id}")
            return self._profiles_cache[user_id]

        try:
            profile = Profile(user_id)
            
            if use_cache:
                self._profiles_cache[user_id] = profile
                logger.debug(f"Profile cached for user: {user_id}")
            
            return profile
            
        except AppError as e:
            logger.error(f"Failed to get profile for user {user_id}: {e}")
            raise

    def remove_from_cache(self, user_id: str) -> bool:
        """Видалити профіль з кешу"""
        if user_id in self._profiles_cache:
            del self._profiles_cache[user_id]
            logger.debug(f"Profile removed from cache for user: {user_id}")
            return True
        return False

    def clear_cache(self) -> None:
        """Очистити кеш профілів"""
        self._profiles_cache.clear()
        logger.debug("Profile cache cleared")

    def get_cached_profiles_count(self) -> int:
        """Отримати кількість кешованих профілів"""
        return len(self._profiles_cache)


# Глобальний екземпляр менеджера профілів
profile_manager = ProfileManager()