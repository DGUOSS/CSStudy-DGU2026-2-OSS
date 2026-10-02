from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="StudyPlanner API",
    description="DGU 공개SW 프로젝트 주간 학습 플래너 API",
    version="0.1.0",
)
app.include_router(health_router)
