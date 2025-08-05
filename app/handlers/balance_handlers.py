from bs4 import BeautifulSoup

from app.handlers.handlers_manager import HttpHandler
from app.handlers.decorators import handler
from app.utils.links import APIEndpoint, build_url

@handler("check_balance")
class CheckBalanceHandler(HttpHandler):
    async def execute(self, task) -> dict:
        client = task.profile.get_client()
        response = await client.get(build_url(APIEndpoint.CHECK_BALANCE))
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")

        return {
            **self._parse_comments(soup),
            **self._parse_chapters(soup),
            **self._parse_diamonds_today(soup),
            **self._parse_daily_rewards(soup),
        }

    def _parse_comments(self, soup) -> dict:
        block = soup.find("div", string=lambda s: s and "Комментариев" in s)
        if block:
            parts = block.text.strip().split()
            read = int(parts[1])
            total = int(parts[3])
            return {
                "written_comments": read,
                "total_comments": total
            }

    def _parse_chapters(self, soup) -> dict:
        block = soup.find("div", string=lambda s: s and "Глав" in s)
        if block:
            parts = block.text.strip().split()
            read = int(parts[1])
            total = int(parts[3])
            return {
                "read chapters": read,
                "max_chapters": total
            }

    def _parse_diamonds_today(self, soup) -> dict:
        received = 0
        spent = 0

        plus_div = soup.find("div", class_="user-quest__totally-title--plus")
        if plus_div:
            try:
                received = int(plus_div.text.strip().replace("+", ""))
            except ValueError:
                received = 0

        minus_div = soup.find("div", class_="user-quest__totally-title--minus")
        if minus_div:
            try:
                spent = int(minus_div.text.strip().replace("-", ""))
            except ValueError:
                spent = 0

        return {
            "diamonds_received_today": received,
            "diamonds_spent_today": spent,
        }

    def _parse_daily_rewards(self, soup) -> dict:
        claimed_day = None
        claimable_day = None

        reward_blocks = soup.find_all("div", class_="daily-rewards-item")
        for item in reward_blocks:
            day_str = item.get("data-day")
            if not day_str:
                continue
            try:
                day = int(day_str)
            except ValueError:
                continue

            exp_block = item.find("div", class_="daily-rewards-item-exp")
            if exp_block:
                classes = exp_block.get("class", [])

                # День, который можно забрать
                if "daily-rewards-item-exp--active" in classes:
                    if claimable_day is None or day > claimable_day:
                        claimable_day = day

                # День, который уже получен
                if "daily-rewards-item-exp--completed" in classes:
                    if claimed_day is None or day > claimed_day:
                        claimed_day = day

        return {
            "claimed_reward_day": claimed_day,
            "claimable_reward_day": claimable_day,
        }


@handler("claim_daily_rewards")
class DailyRewardHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для чтения пака глав"""
        client = task.profile.get_client()
        response = await client.post(build_url(APIEndpoint.CLAIM_AWARD, path_params=task.payload))
        return await response.json()
    
    async def validate_input(self, task):
        """Проверка входных данных"""
        if not isinstance(task.payload, dict):
            raise ValueError("Payload must be a dictionary")

        required_key = "day"
        if required_key not in task.payload:
            raise KeyError(f"Missing required key in payload: {required_key}")
            
        return True