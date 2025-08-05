from app.handlers.handlers_manager import HttpHandler
from app.handlers.decorators import handler
from app.utils.links import APIEndpoint, build_url

@handler("mine_hit")
class MineHitHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для удара по руде"""
        client = task.profile.get_client()
        response = await client.post(build_url(APIEndpoint.MINE_HIT))
        return await response.json()
    

@handler("mine_exchange")
class MineExchangeHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для удара по руде"""
        client = task.profile.get_client()
        response = await client.post(build_url(APIEndpoint.MINE_EXCHANGE))
        return await response.json()
    
    
@handler("mine_upgrade")
class MineUpgradeHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для удара по руде"""
        client = task.profile.get_client()
        response = await client.post(build_url(APIEndpoint.MINE_UPGRADE))
        return await response.json()