# файл: app/execution/interfaces/http_handler.py
"""
Базовый HTTP хендлер для обработки HTTP запросов
"""
from app.execution.interfaces.base_handler import BaseHandler
from app.models.execution_models import ProfileTask
import logging

logger = logging.getLogger(__name__)

class HttpHandler(BaseHandler):
    """Базовый хендлер для HTTP операций"""

    async def cleanup(self, task: ProfileTask):
        try:
            profile = task.profile
            if profile and hasattr(profile, 'http_service') and profile.http_service:
                await profile.http_service.close_client()
        except Exception as e:
            logger.warning(f"HTTP cleanup failed: {e}")
