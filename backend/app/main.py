from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.api import api_v1_router
from app.api.v1.health import router as health_router
from app.importer.pipeline import CurriculumImporter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist (compatible with SQLite dev & PostgreSQL)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        importer = CurriculumImporter(db)
        importer.ensure_class_grades()
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="VidyaFlow Curriculum & Adaptive Learning Platform API for Classes 6–10 (Telangana State Board & ICSE)",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root level health endpoint
app.include_router(health_router, tags=["Health"])

# Direct /api prefix endpoints (Student, Teacher, Chatbot, Parent RAG)
from app.api.v1.vidyaflow_rag import router as vidyaflow_rag_router
app.include_router(vidyaflow_rag_router, prefix="/api")

# API v1 endpoints
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to VidyaFlow Curriculum API",
        "docs": "/docs",
        "health": "/health",
        "api_v1": settings.API_V1_STR,
    }
