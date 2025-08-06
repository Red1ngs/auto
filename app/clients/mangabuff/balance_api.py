from app.utils.links import APIEndpoint, build_url

class BalanceAPI:
    def __init__(self, client):
        self.client = client

    async def get_balance_html(self) -> str:
        """Получить HTML-страницу с информацией о балансе"""
        response = await self.client.get(build_url(APIEndpoint.CHECK_BALANCE))
        return await response.text()

    async def claim_daily_reward(self, payload: dict) -> dict:
        """Запрос на получение ежедневной награды"""
        response = await self.client.post(build_url(APIEndpoint.CLAIM_AWARD, path_params=payload))
        return await response.json()
