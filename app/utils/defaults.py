import time
from typing import Dict, Union

def base_headers() -> Dict[str, str]:
    return {
        "Host": "mangabuff.ru",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "ru,en;q=0.9",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Priority": "u=0, i",
        "User-Agent": "",
        "x-csrf-token": "",
        "x-requested-with": "XMLHttpRequest"
    }

def base_cookie() -> Dict[str, str]:
    return {
        "XSRF-TOKEN": "",
        "mangabuff_session": "",
        "__ddg9_": "",
        "theme": "light"
    }

def base_network_config() -> Dict[str, Union[str, int]]:
    return {
        "cookie": base_cookie(),
        "headers": base_headers(),
        "base_url": "https://mangabuff.ru",
        "data_time": int(time.time() * 1000),
        "retries": 3,
        "timeout": 360
    }
    
def base_profile_config() -> Dict[str, Union[str, int]]:
    return {
        "last_chapter": 0,
        "batch_size": 2,
        "batch_limit": 100,
        "current_mode": "tokens"
    }
    
def base_static_config() -> Dict[str, Union[str, int]]:
    return {
        "reader": {
            "modes": {
                
            }
        }
    }