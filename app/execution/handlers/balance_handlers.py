# app/execution/handlers/balance_handlers.py
from app.parsers.mangabuff.balance_parser import BalanceParser
from app.clients.mangabuff.balance_api import BalanceAPI

from app.execution.interfaces.http_handler import HttpHandler
from app.execution.decorators.handler import handler

from app.utils.validators import require_keys

@handler("check_balance")
class CheckBalanceHandler(HttpHandler):
    async def execute(self, task) -> dict:
        client = task.profile.get_client()
        api = BalanceAPI(client)

        html = await api.get_balance_html()
        parser = BalanceParser(html)

        return parser.parse_all()


@handler("claim_daily_rewards")
class DailyRewardHandler(HttpHandler):
    async def execute(self, task) -> dict:
        client = task.profile.get_client()
        api = BalanceAPI(client)
        return await api.claim_daily_reward(task.payload)

    async def validate_input(self, task):
        require_keys(task.payload, ["day"])
        return True