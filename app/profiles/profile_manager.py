import logging
import json
from pathlib import Path
from typing import Union, Any

from schemas.models import Account_http_data
from exceptions.exceptions import (
        AppError, ProfileNetworkConfigEmptyError
    )

from utils.paths import ACCOUNTS_DIR
from utils.file_utils import FileInitializer
from utils.http_defaults import base_network_config

from handlers.error_handlers import handle_app_errors

from mangabuff.http_client import HttpClient

logger = logging.getLogger(__name__)
 
         
class Profile:
    @handle_app_errors(raise_on_fail=True)
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.storage = ProfileStorage(self)
        self.mangabuff = ProfileHTTP(self)
        self.profile_init()

    @handle_app_errors(raise_on_fail=True)
    def profile_init(self):
        """
        Инициализация профиля.
        Создает директорию профиля, если она не существует.
        """
        self.profile_dir = ACCOUNTS_DIR / self.user_id
        
        FileInitializer.ensure_directory(self.profile_dir, raise_error=True)  
            
        self.reader_dir_path = self.profile_dir / "reader"
        FileInitializer.ensure_directory(self.reader_dir_path, raise_error=True)  
        self.cards_images_dir = self.reader_dir_path / "cards_images"
        FileInitializer.ensure_directory(self.cards_images_dir, raise_error=True)  
        
        self.network_config_path = self.profile_dir / "network_config.json"
        FileInitializer.ensure_json_file(self.network_config_path, 
            default_data= base_network_config(),
            raise_error=True
        )
        
        self.reader_config_path = self.reader_dir_path / "reader_config.json"
        FileInitializer.ensure_json_file(self.reader_config_path, 
            default_data={
                "batch_size": 2,
                "batch_limit": 100,
                "current_mode": "tokens"
            }, 
            raise_error=True
        )
        self.reader_stats_path = self.reader_dir_path / "reader_stats.json"

        self.avatar_path = self.profile_dir / "avatar.png"
             
    
class ProfileStorage:
    @handle_app_errors(raise_on_fail=True)
    def __init__(self, profile: Profile):
        self.profile = profile
        
    @handle_app_errors(raise_on_fail=True)
    def read_json(self, path: str | Path, default: Any = None) -> Any:
        """
        Прочитать JSON-файл и вернуть данные.
        Если файл не существует — вернуть default или пустой dict.
        """
        path = Path(path)
        if not path.exists():
            return default if default is not None else {}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @handle_app_errors(raise_on_fail=True)
    def write_json(
        self,
        data: Any,
        path: str | Path,
        *,
        indent: int = 2,
        sort_keys: bool = False,
        ensure_ascii: bool = False,
        overwrite: bool = True
    ) -> None:
        """
        Сохранить данные в JSON-файл.

        :param data: любые сериализуемые данные (dict, list и т.д.)
        :param path: путь до файла
        :param indent: отступы (по умолчанию 2)
        :param sort_keys: сортировка ключей
        :param ensure_ascii: экранировать юникод (по умолчанию False)
        :param overwrite: если False — выбросит ошибку, если файл уже существует
        """
        path = Path(path)
        if not overwrite and path.exists():
            raise FileExistsError(f"Файл уже существует: {path}")

        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)
            
    def handle_not_found_network_config(self):
        raise ProfileNetworkConfigEmptyError(
            f"Network configuration for profile '{self.profile.user_id}' is empty. Cannot proceed with account-based HTTP client."
        )
      
    
class ProfileHTTP:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.storage = profile.storage
    
    @handle_app_errors(raise_on_fail=True)
    def client(self, use_account: bool = True) -> "HttpClient":
        self.account_http_data = self._get_http_data()

        if use_account:
            if self.account_http_data is None or self.account_http_data.is_default():
                raise ProfileNetworkConfigEmptyError(
                    f"Network configuration for profile '{self.profile.user_id}' is missing or default."
                )
            http_data = self.account_http_data
        else:
            http_data = None

        return HttpClient(http_data, use_account=use_account)

    @handle_app_errors(raise_on_fail=False)
    def _get_http_data(self) -> Union[Account_http_data, None]:
        """
        Получить данные профиля из JSON-файла.
        Если файл не существует, он будет создан.
        """
        FileInitializer.ensure_json_file(
            self.profile.network_config_path,
            default_data=base_network_config(),
            raise_error=True,
            on_error=lambda: self.storage.handle_not_found_network_config()
        )
        
        data = self.storage.read_json(self.profile.network_config_path)
        if not data:
            return None
        
        return Account_http_data(**data)
    
    
class ProfileManager:
    def __init__(self):
        pass
    
    def get_profile(self, user_id: str) -> Union[Profile, None]:
        try:
            profile = Profile(user_id)
            return profile
        except AppError as e:
            print(e)
            raise  
        
profile_manager = ProfileManager()