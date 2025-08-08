# app/clients/quiz_api.py
from typing import List

from app.utils.links import APIEndpoint, build_url
from app.models.payloads.chapter import ReadChapterPayload, TakeCandyPayload, LoadChaptersPayload

class ChapterAPI:
    def __init__(self, client):
        self.client = client
        
    async def load_chapters(self, payload: LoadChaptersPayload) -> dict:
        response = await self.client.post(build_url(APIEndpoint.LOAD_CHAPTERS), payload=payload)
        return await response.json()

    async def read_chapter(self, payload: List[ReadChapterPayload]) -> dict:
        response = await self.client.post(build_url(APIEndpoint.READ_CHAPTER), payload=payload)
        return await response.json()
    
    async def take_candy(self, payload: TakeCandyPayload) -> dict:
        response = await self.client.post(build_url(APIEndpoint.TAKE_CANDY), payload=payload)
        return await response.json()