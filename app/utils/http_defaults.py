from typing import Dict

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

def base_network_config() -> Dict[str, str]:
    return {
        "cookie": base_cookie(),
        "headers": base_headers(),
        "base_url": "https://mangabuff.ru",
        "retries": 3,
        "timeout": 360
    }