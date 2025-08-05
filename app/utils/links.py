from enum import Enum
from dataclasses import dataclass, asdict
from typing import Final, Optional, Dict, Union, Literal

BASE_URL: Final[str] = "https://mangabuff.ru"


class APIEndpoint(str, Enum):
    # Mine module
    CHECK_MINE_BALANCE = "/mine"
    MINE_HIT = "/mine/hit"
    MINE_EXCHANGE = "/mine/exchange"
    MINE_UPGRADE = "/mine/upgrade"

    # Balance module
    CHECK_BALANCE = "/balance"
    CLAIM_AWARD = "/balance/claim/{day}"
    
    # Profile activities module
    CHECK_PROFILE = "/users/{user_id}"
    CHECK_CARDS = "/users/{user_id}/cards"
    WRITE_TO_USER = "/messages/{user_id}"
    
    # Trade module
    CREATE_TRADE = "/trades/create"             # {receiver_id: value, receiver_card_ids: [value], creator_card_ids: [value]}
    ACCEPT_TRADE = "/trades/{trade_id}/accept"
    REJECT_TRADE = "/trades/{trade_id}/reject"
    REJECT_CANCEL = "/trades/{trade_id}/cancel"
    REJECT_ALL_TRADE = "/trades/rejectAll"
    
    # Read module
    READ_CHAPTER = "/addHistory?r=702"          # {items: [{chapter_id: value, manga_id: value}]}
    TAKE_CANDY = "/halloween/takeCandy?r=776"   # {token: value}

@dataclass
class RejectAllQuery:
    type_trade: Literal["sender"]

    def to_query_dict(self) -> Dict[str, Union[str, int]]:
        """Преобразует параметры в словарь для использования в query string"""
        return {
            k: str(v).lower() if isinstance(v, bool) else v
            for k, v in asdict(self).items()
            if v is not None
        }

    def __str__(self) -> str:
        """Удобное строковое представление"""
        return f"RejectAllQuery({self.to_query_dict()})"

@dataclass
class CardsByCategoryQuery:
    category_id: str
    rank: Optional[str] = None
    only_need: Optional[Literal["x", "s", "a", "p", "g", "b", "c", "d", "e", "n", "h", "v", "l"]] = None
    only_anim_part: Optional[bool] = None
    only_animated: Optional[bool] = None
    search: Optional[str] = None
    page: Optional[int] = None
    limit: Optional[int] = None

    def to_query_dict(self) -> Dict[str, Union[str, int]]:
        """Преобразует параметры в словарь для использования в query string"""
        return {
            k: str(v).lower() if isinstance(v, bool) else v
            for k, v in asdict(self).items()
            if v is not None
        }

    def __str__(self) -> str:
        """Удобное строковое представление"""
        return f"GetCardsByCategoryQuery({self.to_query_dict()})"
    

def build_url(
    endpoint: APIEndpoint,
    path_params: Optional[Dict[str, Union[str, int]]] = None,
    query_params: Optional[Union[Dict[str, Union[str, int, bool]], object]] = None,
) -> str:
    path_params = path_params or {}

    path = endpoint.value.format(**path_params)
    url = BASE_URL.rstrip("/") + path

    if query_params:
        if hasattr(query_params, "to_query_dict"):
            query_dict = query_params.to_query_dict()
        elif isinstance(query_params, dict):
            query_dict = {
                k: str(v).lower() if isinstance(v, bool) else v
                for k, v in query_params.items()
                if v is not None
            }
        else:
            raise TypeError("query_params must be dict or have to_query_dict()")

        from urllib.parse import urlencode, quote_plus
        url += "?" + urlencode(query_dict, quote_via=quote_plus)

    return url
