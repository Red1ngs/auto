from dataclasses import dataclass
from typing import Optional, Dict

@dataclass(order=True)
class Proxy:
    id: str
    host: Optional[str] = None 
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Перевіряє, чи є проксі валідним (має хост і порт)."""
        return bool(self.host and self.port)
    
    @property
    def is_default(self) -> bool:
        """Перевіряє, чи є це проксі за замовчуванням (без проксі)."""
        return self.id == "0" or not self.is_valid

    @property
    def as_dict(self) -> Dict[str, str]:
        """Повертає проксі у форматі словника для aiohttp."""
        if not self.is_valid:
            return {}

        auth = f"{self.username}:{self.password}@" if self.username and self.password else ""
        url = f"http://{auth}{self.host}:{self.port}"
        return {
            "http": url,
            "https": url
        }
    
    def __str__(self) -> str:
        if self.is_default:
            return "Proxy(No proxy)"
        return f"Proxy({self.host}:{self.port})"