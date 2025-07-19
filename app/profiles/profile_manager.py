import logging
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from app.execution.models.http_model import AccountHTTPData
from app.execution.models.profile_config_model import AccountReaderSettings
from app.execution.models.profile_stats_model import AccountStats

from app.exceptions.registration_exception import ProfileNetworkConfigEmptyException, ProfileReaderConfigNotFoundException
from app.exceptions.base_exceptions import AppError

from app.utils.paths import ACCOUNTS_DIR
from app.utils.file_utils import FileInitializer
from app.utils.defaults import base_network_config, base_profile_config

from app.handlers.error_handlers import handle_app_errors

from app.mangabuff.http_client import HttpClient

logger = logging.getLogger(__name__)


@dataclass
class ProfilePaths:
    """Централізовані шляхи профілю для кращого управління"""
    profile_dir: Path
    images_dir: Path
    network_config_path: Path
    profile_config_path: Path
    profile_stats_path: Path
    avatar_path: Path

    @classmethod
    def from_user_id(cls, user_id: str) -> "ProfilePaths":
        """Створити ProfilePaths з user_id"""
        profile_dir = ACCOUNTS_DIR / user_id
        
        return cls(
            profile_dir=profile_dir,
            images_dir=profile_dir / "images",
            network_config_path=profile_dir / "network_config.json",
            profile_config_path=profile_dir / "profile_config.json",
            profile_stats_path=profile_dir / "profile_stats.json",
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
            self.paths.images_dir
        ]
        
        for directory in directories:
            FileInitializer.ensure_directory(directory, raise_error=True)
            logger.debug(f"Directory ensured: {directory}")

    def _create_config_files(self) -> None:
        """Створення конфігураційних файлів"""
        config_files = [
            (self.paths.network_config_path, base_network_config()),
            (self.paths.profile_config_path, base_profile_config()),
            (self.paths.profile_stats_path, {})
        ]
        
        for file_path, content in config_files:
            FileInitializer.ensure_file_with_content(
                file_path,
                content=content,
                raise_error=True,
                is_json=True
            )
            logger.debug(f"Config file ensured: {file_path}")

    async def close(self):
        """Вызывайте при завершении работы с профилем, чтобы закрыть HTTP-клиент"""
        await self.http.close()
        
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
        
        self.profile_settings = self._load_profile_settings()
        self.profile_stats = self._load_profile_stats()
        
        logger.info(f"Storage initialized for profile: {self.profile.user_id}")

    def _load_json_config(self, path: Path, model_cls, *, default=None, raise_error=False, on_error=None) -> Optional[Any]:
        FileInitializer.ensure_file_with_content(
            path,
            content=default() if default else None,
            is_json=True,
            raise_error=raise_error,
            on_error=on_error,
        )
        data = model_cls.from_json(path)
        logger.debug(f"{model_cls.__name__} loaded for profile: {self.profile.user_id}")
        return data

    def _load_profile_settings(self) -> Optional[AccountReaderSettings]:
        """Завантажити налаштування профілю"""
        return self._load_json_config(
            self.profile.paths.profile_config_path,
            AccountReaderSettings,
            default=base_profile_config,
            raise_error=True,
            on_error=self._handle_missing_reader_config
        )

    def _load_profile_stats(self) -> Optional[AccountStats]:
        """Завантажити статистику профілю"""
        return self._load_json_config(
            self.profile.paths.profile_stats_path,
            AccountStats
        )

    @handle_app_errors(raise_on_fail=False)
    def _load_http_data(self) -> Optional[AccountHTTPData]:
        """Завантажити HTTP-дані профілю"""
        return self._load_json_config(
            self.profile.paths.network_config_path,
            AccountHTTPData,
            default=base_network_config,
            raise_error=True,
            on_error=self._handle_missing_network_config
        )


    def _handle_missing_network_config(self) -> None:
        """Обробник відсутнього мережевого конфігу"""
        error_msg = (
            f"Network configuration for profile '{self.profile.user_id}' is empty. "
            "Cannot proceed with account-based HTTP client."
        )
        logger.error(error_msg)
        raise ProfileNetworkConfigEmptyException(error_msg)
    
    def _handle_missing_reader_config(self) -> None:
        """Обробник відсутнього читачевого конфігу"""
        error_msg = (
            f"Reader configuration for profile '{self.profile.user_id}' is empty. "
            "Cannot create profile."
        )
        logger.error(error_msg)
        raise ProfileReaderConfigNotFoundException(error_msg)
        
    def reload_profile_settings(self) -> bool:
        """Перезавантажити налаштування профілю"""
        try:
            self.profile_settings = self._load_profile_settings()
            return self.profile_settings is not None
        except Exception as e:
            logger.error(f"Failed to reload profile settings: {e}")
            return False

    def reload_profile_stats(self) -> bool:
        """Перезавантажити статистику профілю"""
        try:
            self.profile_stats = self._load_profile_stats()
            return self.profile_stats is not None
        except Exception as e:
            logger.error(f"Failed to reload profile stats: {e}")
            return False
        
    @property
    def is_initialized(self) -> bool:
        """Перевірити, чи ініціалізовано сховище"""
        return all([
            self.http_data is not None,
            self.profile_settings is not None,
            self.profile_stats is not None
        ])

    def __str__(self) -> str:
        return f"ProfileStorage(user_id={self.profile.user_id}, initialized={self.is_initialized})"

    def __repr__(self) -> str:
        return self.__str__()


class ProfileHTTP:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.storage = profile.storage
        self._client: Optional[HttpClient] = None
    
    @handle_app_errors(raise_on_fail=True)
    def get_client(self, use_account: bool = True) -> HttpClient:
        if self._client is None:
            self.http_data = self.storage._load_http_data()
            if use_account:
                if not self._is_account_data_valid():
                    error_msg = (
                        f"Network configuration for profile '{self.profile.user_id}' "
                        "is missing or default."
                    )
                    raise ProfileNetworkConfigEmptyException(error_msg)
                http_data = self.http_data
            else:
                http_data = None
            self._client = HttpClient(http_data, use_account=use_account)
        return self._client

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None

    def _is_account_data_valid(self) -> bool:
        return (
            self.http_data is not None and
            not self.http_data.is_default()
        )
 

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