# файл: app/execution/handlers/quiz_handlers.py
from app.execution.interfaces.http_handler import HttpHandler
from app.execution.decorators.handler import handler

from app.clients.mangabuff.mining_api import MiningAPI

@handler("mine_hit")
class MineHitHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для удара по руде"""
        client = task.profile.get_client()
        api = MiningAPI(client)
        
        return await api.mine_hit()
    

@handler("mine_exchange")
class MineExchangeHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для удара по руде"""
        client = task.profile.get_client()
        api = MiningAPI(client)
        
        return await api.mine_exchange()
    
    
@handler("mine_upgrade")
class MineUpgradeHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для удара по руде"""
        client = task.profile.get_client()
        api = MiningAPI(client)
        
        return await api.mine_upgrade()