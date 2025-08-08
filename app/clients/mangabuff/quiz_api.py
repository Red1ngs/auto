# app/clients/quiz_api.py
from app.utils.links import APIEndpoint, build_url
from app.models.payloads.quiz import AnswerPayload

class QuizAPI:
    def __init__(self, client):
        self.client = client

    async def start_quiz(self):
        response = await self.client.post(build_url(APIEndpoint.START_QUIZ))
        return await response.json()

    async def answer_quiz(self, payload: AnswerPayload):
        response = await self.client.post(build_url(APIEndpoint.ANSWER_QUIZ), payload)
        return await response.json()