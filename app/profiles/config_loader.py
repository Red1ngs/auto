import logging
from typing import Optional,  Any
from pathlib import Path

from app.models.profile_models import AccountHTTPData, AccountReaderSettings, StaticConfig
from app.utils.paths import Paths

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Отвечает только за загрузку конфигурационных файлов."""
    
    def load_config(self, path: Path, model_cls) -> Optional[Any]:
        """
        Универсальный метод загрузки JSON конфигурации.
        
        Args:
            path: Путь к конфигурационному файлу
            model_cls: Класс модели для десериализации
            
        Returns:
            Загруженная конфигурация или None
        """
        try:
            data = model_cls.from_json(path)
            logger.debug(f"{model_cls.__name__} loaded from: {path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load {model_cls.__name__} from {path}: {e}")
            return None

    def load_network_config(self, paths: Paths) -> Optional[AccountHTTPData]:
        """Загрузить сетевую конфигурацию."""
        return self.load_config(paths.network_config_path, AccountHTTPData)
        
    def load_profile_settings(self, paths: Paths) -> Optional[AccountReaderSettings]:
        """Загрузить настройки профиля."""
        return self.load_config(paths.profile_config_path, AccountReaderSettings)
        
    def load_static_config(self, paths: Paths) -> Optional[StaticConfig]:
        """Загрузить статическую конфигурацию."""
        return self.load_config(paths.static_config_path, StaticConfig)
