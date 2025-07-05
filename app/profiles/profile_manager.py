import logging
from typing import Union, Dict

from schemas.models import Account_http_data
from schemas.exceptions import (
        ProfileDirNotFoundError, ProfileNetworkConfigNotFoundError,
        AppError, ProfileNetworkConfigEmptyError
    )

from utils.paths import ACCOUNTS_DIR
from utils.json import read_json, write_json
from utils.decorators import handle_app_errors

from http.http_client import HttpClient

logger = logging.getLogger(__name__)

def base_headers() -> dict:
    return {
        "Host": "mangabuff.ru",
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "ru,en;q=0.9",
        "content-type": "application/json; charset=utf-8",
        "origin": "https://mangabuff.ru",
        "user-agent": "",
        "x-csrf-token": "",
        "x-requested-with": "XMLHttpRequest"
    }
        
        
class Profile:
    @handle_app_errors(raise_on_fail=True)
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.profile_dir = ACCOUNTS_DIR / user_id
        if not self.profile_dir.exists():
            raise ProfileDirNotFoundError(f"Profile directory for user ID {user_id} does not exist.")
    
    @handle_app_errors(raise_on_fail=True)
    def http_client(self, use_account: bool = True) -> "HttpClient":
        self.account_http_data = self._get_http_data()
        
        if use_account:
            if self.account_http_data is None:
                raise ProfileNetworkConfigEmptyError(
                    f"Network configuration for profile '{self.user_id}' is empty. Cannot proceed with account-based HTTP client."
                )
            else:
                http_data = self.account_http_data.model_dump()
        else:
            http_data = {"headers": {}, "cookie": {}}
        
        return HttpClient(http_data, use_account=use_account)

    @handle_app_errors(raise_on_fail=False)
    def _get_http_data(self) -> Union[Account_http_data, None]:
        """
        Получить данные профиля из JSON-файла.
        Если файл не существует, он будет создан.
        """
        network_data_path = self.profile_dir / "network_config.json"
        if not network_data_path.exists():
            raise ProfileNetworkConfigNotFoundError(
                f"Profile data file does not exist: {network_data_path}", 
                on_error=lambda: write_json({
                    "cookie": {},
                    "headers": base_headers()   
                }, network_data_path))
        
        data = read_json(network_data_path)
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