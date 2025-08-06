# app/clients/quiz_api.py
from app.utils.links import APIEndpoint, build_url

class QuizAPI:
    def __init__(self, client):
        self.client = client

    async def start_quiz(self):
        response = await self.client.post(build_url(APIEndpoint.START_QUIZ))
        return await response.json()

    async def answer_quiz(self, payload: dict):
        response = await self.client.post(build_url(APIEndpoint.ANSWER_QUIZ), payload)
        return await response.json()