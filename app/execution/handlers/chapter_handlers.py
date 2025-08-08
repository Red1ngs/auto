# app/execution/handlers/quiz_handlers.py
from app.clients.mangabuff.chapter_api import ChapterAPI

from app.execution.interfaces.http_handler import HttpHandler
from app.execution.decorators.handler import handler

from app.utils.validators import require_keys

@handler("load_chapters")
class LoadChaptersHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для загрузки глав"""
        client = task.profile.get_client()
        api = ChapterAPI(client)
        
        return await api.load_chapters(task.payload)
        
    async def validate_input(self, task):
        """Проверка входных данных"""
        require_keys(task.payload, ["manga_id"])
        return True


@handler("chapter_read")
class ChapterReadHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для чтения пака глав"""
        client = task.profile.get_client()
        api = ChapterAPI(client)
        
        return await api.read_chapter(task.payload)
    
    async def validate_input(self, task):
        """Проверка входных данных"""
        require_keys(task.payload, ["items"])
        return True
            
            
@handler("take_candy")
class TakeCandyHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для получения конфет"""
        client = task.profile.get_client()
        api = ChapterAPI(client)
        
        return await api.take_candy(task.payload)
    
    async def validate_input(self, task):
        """Проверка входных данных"""
        require_keys(task.payload, ["candy_token"])
        return True