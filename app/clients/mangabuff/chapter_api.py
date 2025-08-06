# app/clients/quiz_api.py
from typing import List

from app.utils.links import APIEndpoint, build_url
from app.models.payloads import ReadChapterPayload

class ChapterAPI:
    def __init__(self, client):
        self.client = client

    async def read_chapter(self, payload: List[ReadChapterPayload]) -> dict:
        response = await self.client.post(build_url(APIEndpoint.READ_CHAPTER), path_params=payload)
        return await response.json()
    
    async def take_candy(self, payload: dict) -> dict:
        response = await self.client.post(build_url(APIEndpoint.TAKE_CANDY), path_params=payload)
        return await response.json()