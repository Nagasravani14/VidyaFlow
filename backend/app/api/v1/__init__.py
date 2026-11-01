from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.boards import router as boards_router
from app.api.v1.subjects import router as subjects_router
from app.api.v1.chapters import router as chapters_router
from app.api.v1.topics import router as topics_router
from app.api.v1.search import router as search_router
from app.api.v1.tutor import router as tutor_router
from app.api.v1.ai_questions import router as ai_questions_router
from app.api.v1.practice_eval import router as practice_eval_router
from app.api.v1.vidyaflow_rag import router as vidyaflow_rag_router
from app.api.v1.chapter_quiz import router as chapter_quiz_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router)
api_v1_router.include_router(boards_router)
api_v1_router.include_router(subjects_router)
api_v1_router.include_router(chapters_router)
api_v1_router.include_router(topics_router)
api_v1_router.include_router(search_router)
api_v1_router.include_router(tutor_router)
api_v1_router.include_router(ai_questions_router)
api_v1_router.include_router(practice_eval_router)
api_v1_router.include_router(vidyaflow_rag_router)
api_v1_router.include_router(chapter_quiz_router)

__all__ = ["api_v1_router"]
