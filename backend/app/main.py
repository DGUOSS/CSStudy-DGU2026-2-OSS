from fastapi import APIRouter, FastAPI

from app.features.admin.misconception_probes import router as admin_probes_router
from app.features.admin.router import router as admin_router
from app.features.auth.router import router as auth_router
from app.features.course_requests.router import router as course_requests_router
from app.features.courses.router import router as courses_router
from app.features.exams.router import router as exams_router
from app.features.mastery.router import router as mastery_router
from app.features.materials.router import router as materials_router
from app.features.my_subjects.router import router as my_subjects_router
from app.features.problems.router import router as problems_router

app = FastAPI(title="dgu-study", version="0.2.0")

api = APIRouter(prefix="/api/v1")


@api.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# 기능을 추가하면 여기에 한 줄 등록한다
api.include_router(auth_router)
api.include_router(courses_router)
api.include_router(materials_router)
api.include_router(problems_router)
api.include_router(mastery_router)
api.include_router(course_requests_router)
api.include_router(admin_router)
api.include_router(admin_probes_router)
api.include_router(my_subjects_router)
api.include_router(exams_router)

app.include_router(api)
