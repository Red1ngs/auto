# app/clients/quiz_api.py
from app.utils.links import APIEndpoint, build_url

class MiningAPI:
    def __init__(self, client):
        self.client = client

    async def mine_hit(self) -> dict:
        response = await self.client.post(build_url(APIEndpoint.MINE_HIT))
        return await response.json()
    
    async def mine_exchange(self) -> dict:
        response = await self.client.post(build_url(APIEndpoint.MINE_EXCHANGE))
        return await response.json()
    
    async def mine_upgrade(self) -> dict:
        response = await self.client.post(build_url(APIEndpoint.MINE_UPGRADE))
        return await response.json()
    