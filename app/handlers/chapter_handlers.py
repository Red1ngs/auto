from app.handlers.handlers_manager import HttpHandler
from app.handlers.decorators import handler
from app.utils.links import APIEndpoint, build_url

@handler("chapter_read")
class ChapterReadHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для чтения пака глав"""
        client = task.profile.get_client()
        chapters_pack = task.payload["chapters_pack"]
        response = await client.post(build_url(APIEndpoint.READ_CHAPTER), {"items": chapters_pack})
        return await response.json()
    
    async def validate_input(self, task):
        """Проверка входных данных"""
        if not isinstance(task.payload, dict):
            raise ValueError("Payload must be a dictionary")

        required_keys = ["chapters_pack"]
        for key in required_keys:
            if key not in task.payload:
                raise KeyError(f"Missing required key in payload: {key}")
            
        return True
            
            
@handler("take_candy")
class TakeCandyHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для получения конфет"""
        client = task.profile.get_client()
        response = await client.post(build_url(APIEndpoint.TAKE_CANDY), path_params=task.payload)
        return await response.json()
    
    async def validate_input(self, task):
        """Проверка входных данных"""
        if not isinstance(task.payload, dict):
            raise ValueError("Payload must be a dictionary")

        required_key = "candy_token"
        if required_key not in task.payload:
            raise KeyError(f"Missing required key in payload: {required_key}")
            
        return True