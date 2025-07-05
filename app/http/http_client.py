import logging
import json
import requests

from typing import Dict, Union, TYPE_CHECKING

from utils.decorators import log_http_request

if TYPE_CHECKING:
    from schemas.models import Headers, Cookie

logger = logging.getLogger(__name__)

class HttpClient:
    def __init__(self, http_data: Dict[str, Union[Headers, Cookie]], *, use_account: bool = True):
        self.headers = http_data["headers"].model_dump() if use_account else {}
        self.cookie = http_data["cookie"].model_dump() if use_account else {}
        self.use_account = use_account

    @log_http_request("POST")
    def post(self, url: str, payload: Dict, *, retries=3, timeout=360.0) -> requests.Response | None:
        return requests.post(
            url,
            headers=self.headers,
            cookies=self.cookie,
            data=json.dumps(payload),
            timeout=timeout
        )

    @log_http_request("GET")
    def get(self, url: str, payload=None, *, retries=3, timeout=360.0) -> requests.Response | None:
        return requests.get(
            url,
            headers=self.headers,
            cookies=self.cookie,
            params=payload,
            timeout=timeout
        )
