# файл: app/execution/handlers/quiz_handlers.py
from app.execution.interfaces.http_handler import HttpHandler
from app.execution.decorators.handler import handler
from app.utils.validators import require_keys
from app.clients.mangabuff.quiz_api import QuizAPI

@handler("quiz_start")
class StartQuizHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для начала квиза"""
        api = QuizAPI(task.profile.get_client())
        data = await api.start_quiz()
        question = data.get("question", {})
        return question
        

@handler("answer_quiz")
class AnswerQuizHandler(HttpHandler):
    async def execute(self, task) -> dict:
        """Обработчик для начала квиза"""
        api = QuizAPI(task.profile.get_client())
        data = await api.start_quiz()
        question = data.get("question", {})
        return question
        
    async def validate_input(self, task):
        """Проверка входных данных"""
        require_keys(task.payload, ["answer"])
        return True
        
