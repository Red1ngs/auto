from bs4 import BeautifulSoup

class BalanceParser:
    def __init__(self, html: str):
        self.soup = BeautifulSoup(html, "html.parser")

    def parse_all(self) -> dict:
        return {
            **self._parse_comments(),
            **self._parse_chapters(),
            **self._parse_diamonds_today(),
            **self._parse_daily_rewards(),
        }

    def _parse_comments(self) -> dict:
        block = self.soup.find("div", string=lambda s: s and "Комментариев" in s)
        if block:
            parts = block.get_text(strip=True).split()
            if len(parts) >= 4:
                return {
                    "written_comments": int(parts[1]),
                    "total_comments": int(parts[3])
                }
        return {}

    def _parse_chapters(self) -> dict:
        block = self.soup.find("div", string=lambda s: s and "Глав" in s)
        if block:
            parts = block.get_text(strip=True).split()
            if len(parts) >= 4:
                return {
                    "read_chapters": int(parts[1]),
                    "max_chapters": int(parts[3])
                }
        return {}

    def _parse_diamonds_today(self) -> dict:
        received = self._parse_int_from_class("user-quest__totally-title--plus", "+")
        spent = self._parse_int_from_class("user-quest__totally-title--minus", "-")
        return {
            "diamonds_received_today": received,
            "diamonds_spent_today": spent,
        }

    def _parse_int_from_class(self, class_name: str, symbol: str) -> int:
        div = self.soup.find("div", class_=class_name)
        if div:
            try:
                return int(div.get_text(strip=True).replace(symbol, ""))
            except (ValueError, AttributeError):
                return 0
        return 0

    def _parse_daily_rewards(self) -> dict:
        claimed_day = None
        claimable_day = None

        for item in self.soup.find_all("div", class_="daily-rewards-item"):
            day_str = item.get("data-day")
            if not day_str or not day_str.isdigit():
                continue
            day = int(day_str)

            exp_block = item.find("div", class_="daily-rewards-item-exp")
            if not exp_block:
                continue
            classes = exp_block.get("class", [])

            if "daily-rewards-item-exp--active" in classes:
                claimable_day = max(claimable_day or 0, day)

            if "daily-rewards-item-exp--completed" in classes:
                claimed_day = max(claimed_day or 0, day)

        return {
            "claimed_reward_day": claimed_day,
            "claimable_reward_day": claimable_day,
        }
