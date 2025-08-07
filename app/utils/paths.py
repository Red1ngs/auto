from pathlib import Path
from dataclasses import dataclass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PROFILE_DIR = PROJECT_ROOT / "profiles"
PROXY_DIR = PROJECT_ROOT / "clients/proxy"
ACCOUNTS_DIR = PROJECT_ROOT.parent / "accounts"

@dataclass
class Paths:
    account_dir: Path | None = None
    images_dir: Path | None = None
    static_config_path: Path | None = None
    network_config_path: Path | None = None
    profile_config_path: Path | None = None
    profile_stats_path: Path | None = None
    avatar_path: Path | None = None

    @classmethod
    def from_profile_id(cls, profile_id: str, base_dir: Path = ACCOUNTS_DIR) -> "Paths":
        """
        Створити налаштовані шляхи для конкретного профілю.
        """
        account_dir = base_dir / profile_id
        return cls(
            account_dir=account_dir,
            images_dir=account_dir / "images",
            static_config_path=PROFILE_DIR / "static_config.json",
            network_config_path=account_dir / "network_config.json",
            profile_config_path=account_dir / "profile_config.json",
            profile_stats_path=account_dir / "profile_stats.json",
            avatar_path=account_dir / "avatar.png"
        )

    @classmethod
    def global_paths(cls) -> "Paths":
        """
        Повертає лише глобальні шляхи (не пов'язані з конкретним профілем).
        """
        return cls(static_config_path=PROFILE_DIR / "static_config.json")

    def exists(self) -> bool:
        """
        Перевірка існування основного каталогу профілю (можна розширити).
        """
        return self.account_dir.exists() if self.account_dir else False
