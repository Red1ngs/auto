import logging
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from app.models.profile_models import AccountHTTPData, AccountReaderSettings, StaticConfig

from app.exceptions.registration_exception import ProfileNetworkConfigEmptyException, ProfileReaderConfigNotFoundException
from app.exceptions.path_exceptions import StaticConfigMissingException
from app.exceptions.base_exceptions import AppError

from app.utils.paths import ACCOUNTS_DIR
from app.utils.file_utils import FileInitializer
from app.utils.defaults import base_network_config, base_profile_config, base_static_config

from app.handlers.error_handlers import handle_app_errors

from app.mangabuff.http_client import HttpClient
from app.proxy.proxy_manager import proxy_manager

logger = logging.getLogger(__name__)


@dataclass
class ProfilePaths:
    """
    Централізовані шляхи профілю для кращого управління.
    
    Attributes:
        account_dir: Основна директорія облікового запису
        images_dir: Директорія для зображень
        static_config_path: Шлях до статичної конфігурації
        network_config_path: Шлях до мережевої конфігурації
        profile_config_path: Шлях до конфігурації профілю
        profile_stats_path: Шлях до статистики профілю
        avatar_path: Шлях до аватара
    """
    account_dir: Path
    images_dir: Path
    static_config_path: Path
    network_config_path: Path
    profile_config_path: Path
    profile_stats_path: Path
    avatar_path: Path

    @classmethod
    def from_profile_id(cls, profile_id: str) -> "ProfilePaths":
        """
        Створити ProfilePaths з profile_id.
        
        Args:
            profile_id: Унікальний ідентифікатор профілю
            
        Returns:
            ProfilePaths: Налаштовані шляхи для профілю
        """
        profile_dir = ACCOUNTS_DIR.parent
        account_dir = ACCOUNTS_DIR / profile_id
        
        return cls(
            account_dir=account_dir,
            static_config_path=profile_dir / "static_config.json",
            images_dir=account_dir / "images",
            network_config_path=account_dir / "network_config.json",
            profile_config_path=account_dir / "profile_config.json",
            profile_stats_path=account_dir / "profile_stats.json",
            avatar_path=account_dir / "avatar.png"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE STORAGE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class ProfileStorage:
    """
    Клас для управління зберіганням даних профілю.
    
    Відповідає за завантаження, збереження та валідацію
    конфігураційних файлів профілю.
    """
    
    def __init__(self, profile: "Profile"):
        self.profile = profile
        self._initialize_storage()

    @handle_app_errors(raise_on_fail=True)
    def _initialize_storage(self) -> None:
        """Ініціалізація сховища профілю."""
        logger.info(f"Initializing storage for profile: {self.profile.profile_id}")
        
        self.profile_settings = self._load_profile_settings()
        self.static = self._load_static_config()
        
        logger.info(f"Storage initialized for profile: {self.profile.profile_id}")
        
        
    def _load_json_config(self, path: Path, model_cls) -> Optional[Any]:
        """
        Універсальний метод завантаження JSON конфігурації.
        
        Args:
            path: Шлях до конфігураційного файлу
            model_cls: Клас моделі для десеріалізації
            
        Returns:
            Завантажена конфігурація або None
        """
        data = model_cls.from_json(path)
        logger.debug(f"{model_cls.__name__} loaded for profile: {self.profile.profile_id}")
        return data

    def _load_profile_settings(self) -> Optional[AccountReaderSettings]:
        """Завантажити налаштування профілю."""
        return self._load_json_config(
            self.profile.paths.profile_config_path,
            AccountReaderSettings
        )
        
    def _load_static_config(self) -> Optional[StaticConfig]:
        """Завантажити статичну конфігурацію."""
        print(self.profile.paths.static_config_path)
        return self._load_json_config(
            self.profile.paths.static_config_path,
            StaticConfig
        )


    def _handle_missing_network_config(self) -> None:
        """Обробник відсутнього мережевого конфігу."""
        error_msg = (
            f"Network configuration for profile '{self.profile.profile_id}' is empty. "
            "Cannot proceed with account-based HTTP client."
        )
        logger.error(error_msg)
        raise ProfileNetworkConfigEmptyException(error_msg)
    
    def _handle_missing_reader_config(self) -> None:
        """Обробник відсутнього читачевого конфігу."""
        error_msg = (
            f"Reader configuration for profile '{self.profile.profile_id}' is empty. "
            "Cannot create profile."
        )
        logger.error(error_msg)
        raise ProfileReaderConfigNotFoundException(error_msg)
    
    def _handle_missing_static_config(self):
        """Обробник відсутнього статичного конфігу."""
        error_msg = "App config is missing. Please ensure the static_config.json file exists in the app directory."
        logger.error(error_msg)
        raise StaticConfigMissingException(message=error_msg)


    def reload_profile_settings(self) -> bool:
        """
        Перезавантажити налаштування профілю.
        
        Returns:
            bool: True якщо успішно перезавантажено, False в іншому випадку
        """
        try:
            self.profile_settings = self._load_profile_settings()
            return self.profile_settings is not None
        except Exception as e:
            logger.error(f"Failed to reload profile settings: {e}")
            return False

    def reload_profile_stats(self) -> bool:
        """
        Перезавантажити статистику профілю.
        
        Returns:
            bool: True якщо успішно перезавантажено, False в іншому випадку
        """
        try:
            self.profile_stats = self._load_profile_stats()
            return self.profile_stats is not None
        except Exception as e:
            logger.error(f"Failed to reload profile stats: {e}")
            return False


    @property
    def is_initialized(self) -> bool:
        """Перевірити, чи ініціалізовано сховище."""
        return all([
            self.http_data is not None,
            self.profile_settings is not None,
            self.profile_stats is not None
        ])

    def __str__(self) -> str:
        return f"ProfileStorage(profile_id={self.profile.profile_id}, initialized={self.is_initialized})"

    def __repr__(self) -> str:
        return self.__str__()


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE HTTP CLIENT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class ProfileHTTP:
    """
    Клас для управління HTTP-клієнтом профілю.
    
    Відповідає за створення та налаштування HTTP-клієнта,
    управління проксі та валідацію мережевих даних.
    """
    
    def __init__(self, profile: "Profile"):
        self.profile = profile
        self.storage = profile.storage
        
        self.proxy = None
        self._client: Optional[HttpClient] = None

    @property
    def http_data(self) -> Optional[AccountHTTPData]:
        """HTTP-дані профілю."""
        return self.storage._load_json_config(
            self.profile.paths.network_config_path,
            AccountHTTPData
        )

    @handle_app_errors(raise_on_fail=True)
    def get_client(self, use_account: bool = True) -> HttpClient:
        """
        Отримати HTTP-клієнт для профілю.
        
        Args:
            use_account: Чи використовувати дані облікового запису
            
        Returns:
            HttpClient: Налаштований HTTP-клієнт
            
        Raises:
            ProfileNetworkConfigEmptyException: Якщо мережева конфігурація відсутня
        """
        if self._client is None:
            if use_account:
                if not self._is_account_data_valid():
                    error_msg = (
                        f"Network configuration for profile '{self.profile.profile_id}' "
                        "is missing or default."
                    )
                    raise ProfileNetworkConfigEmptyException(error_msg)
                data = self.http_data
            else:
                data = None
            self._client = HttpClient(data, use_account=use_account)
            if int(self.proxy.id):
                self._client.set_proxy(self.proxy.as_dict)
        return self._client

    def put_proxy(self, proxy_id: Optional[str]) -> None:
        """
        Додати проксі до профілю, якщо вказаний ID дійсний.
        """
        if not proxy_id:
            return

        proxy = proxy_manager.get(proxy_id)
        
        if not proxy:
            return

        print("_" * 40)
        self.proxy = proxy

    async def close(self):
        """Закрити HTTP-клієнт та очистити ресурси."""
        if self._client:
            await self._client.close()
            self._client = None

    def _is_account_data_valid(self) -> bool:
        """
        Перевірити валідність даних облікового запису.
        
        Returns:
            bool: True якщо дані валідні, False в іншому випадку
        """
        return (
            self.http_data is not None and
            not self.http_data.is_default()
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PROFILE CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class Profile:
    """
    Основний клас профілю користувача.
    
    Координує роботу між зберіганням даних, HTTP-клієнтом
    та конфігураційними файлами профілю.
    
    Attributes:
        profile_id: Унікальний ідентифікатор профілю
        paths: Шляхи до файлів та директорій профілю
        storage: Менеджер зберігання даних
        http: Менеджер HTTP-клієнта
    """
    
    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        self.paths = ProfilePaths.from_profile_id(profile_id)
        
        self.storage = ProfileStorage(self)
        self._initialize_profile()
        
        self.http = ProfileHTTP(self)


    @handle_app_errors(raise_on_fail=True)
    def _initialize_profile(self) -> None:
        """Ініціалізація профілю та створення необхідних директорій і файлів."""
        logger.info(f"Initializing profile: {self.profile_id}")
        
        # Створення директорій
        self._create_directories()
        
        # Створення конфігураційних файлів
        self._create_config_files()
        
        logger.info(f"Profile initialized successfully: {self.profile_id}")

    def _create_directories(self) -> None:
        """Створення необхідних директорій."""
        directories = [
            self.paths.images_dir
        ]
        
        for directory in directories:
            FileInitializer.ensure_directory(directory, raise_error=True)
            logger.debug(f"Directory ensured: {directory}")

    def _create_config_files(self) -> None:
        """Створення конфігураційних файлів."""
        config_files = [
            (self.paths.network_config_path, base_network_config(), True, self.storage._handle_missing_network_config),
            (self.paths.profile_config_path, base_profile_config(), True, self.storage._handle_missing_reader_config),
            (self.paths.static_config_path, base_static_config(), True, self.storage._handle_missing_static_config)
        ]
        
        for file_path, default, raise_error, on_error in config_files:
            FileInitializer.ensure_file_with_content(
                file_path,
                content=default,
                is_json=True, 
                raise_error=raise_error,
                on_error=on_error
            )
            logger.debug(f"Config file ensured: {file_path}")

    def __str__(self) -> str:
        return f"Profile(profile_id='{self.profile_id}')"

    def __repr__(self) -> str:
        return f"Profile(profile_id='{self.profile_id}', account_dir='{self.paths.account_dir}')"


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class ProfileManager:
    """
    Менеджер профілів для управління множинними профілями.
    
    Забезпечує централізоване управління профілями з підтримкою
    кешування для покращення продуктивності.
    
    Attributes:
        _profiles_cache: Внутрішній кеш профілів
    """
    
    def __init__(self):
        self._profiles_cache: Dict[str, Profile] = {}
        logger.info("ProfileManager initialized")

    def get_profile(self, profile_id: str, use_cache: bool = True) -> Profile:
        """
        Отримати профіль за profile_id.
        
        Args:
            profile_id: Унікальний ідентифікатор профілю
            use_cache: Чи використовувати кешування
            
        Returns:
            Profile: Профіль користувача
            
        Raises:
            AppError: При помилці створення або завантаження профілю
        """
        if use_cache and profile_id in self._profiles_cache:
            logger.debug(f"Returning cached profile for profile: {profile_id}")
            return self._profiles_cache[profile_id]

        try:
            profile = Profile(profile_id)
            
            if use_cache:
                self._profiles_cache[profile_id] = profile
                logger.debug(f"Profile cached for profile: {profile_id}")
            
            return profile
            
        except AppError as e:
            logger.error(f"Failed to get profile for profile {profile_id}: {e}")
            raise

    def remove_from_cache(self, profile_id: str) -> bool:
        """
        Видалити профіль з кешу.
        
        Args:
            profile_id: Ідентифікатор профілю для видалення
            
        Returns:
            bool: True якщо профіль було видалено, False якщо його не було в кеші
        """
        if profile_id in self._profiles_cache:
            del self._profiles_cache[profile_id]
            logger.debug(f"Profile removed from cache for profile: {profile_id}")
            return True
        return False

    def clear_cache(self) -> None:
        """Очистити кеш профілів."""
        self._profiles_cache.clear()
        logger.debug("Profile cache cleared")

    def get_cached_profiles_count(self) -> int:
        """
        Отримати кількість кешованих профілів.
        
        Returns:
            int: Кількість профілів у кеші
        """
        return len(self._profiles_cache)


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

# Глобальний екземпляр менеджера профілів
profile_manager: ProfileManager = ProfileManager()