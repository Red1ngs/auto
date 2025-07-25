from typing import Optional, Dict

from dataclasses import dataclass

@dataclass(order=True)
class Proxy:
    id: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None

    @property
    def as_dict(self) -> Dict[str, str]:
        auth = f"{self.username}:{self.password}@" if self.username and self.password else ""
        url = f"http://{auth}{self.host}:{self.port}"
        return {
            "http": url,
            "https": url
        }
    