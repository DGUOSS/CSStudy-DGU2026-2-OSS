from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.features.admin.router import router as admin_router
from app.features.auth.router import router as auth_router
from app.features.catalog.router import router as catalog_router
from app.features.course_requests.router import router as course_requests_router
from app.features.courses.router import router as courses_router
from app.features.department_notices.router import router as department_notices_router
from app.features.enrollments.router import router as enrollments_router
from app.features.exams.router import router as exams_router
from app.features.mastery.router import router as mastery_router
from app.features.materials.router import router as materials_router
from app.features.misconceptions.router import router as misconceptions_router
from app.features.notices.router import router as notices_router
from app.features.papers.router import router as papers_router
from app.features.problems.router import router as problems_router
from app.features.professor_summaries.router import router as professor_summaries_router
from app.features.reviews.router import router as reviews_router
from app.features.structure import service as _structure_hooks  # noqa: F401  (교안 저장 시 자동 챕터·개념)
from app.features.study_groups.router import router as study_groups_router
from app.features.team_project.router import router as team_project_router
from app.services import llm


@asynccontextmanager
async def lifespan(_: FastAPI):
    llm.warm_up()
    _startup_backfill()
    yield


def _startup_backfill() -> None:
    """서버를 켤 때 뒤에서: 챕터·개념이 없는 교안을 채우고, 그다음 오개념이 빠진 객관식을 채운다."""
    import threading

    from app.core.db import engine
    from app.features.misconceptions import service as misconceptions
    from app.features.structure import service as structure

    if not structure.enabled():
        return

    def run() -> None:
        structure.backfill(engine)
        misconceptions.backfill(engine)

    threading.Thread(target=run, daemon=True).start()


app = FastAPI(title="dgu-study", version="0.2.0", lifespan=lifespan)

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
api.include_router(enrollments_router)
api.include_router(catalog_router)
api.include_router(professor_summaries_router)
api.include_router(exams_router)
api.include_router(reviews_router)
api.include_router(papers_router)
api.include_router(misconceptions_router)

api.include_router(notices_router)

api.include_router(department_notices_router)

api.include_router(study_groups_router)
api.include_router(team_project_router)

app.include_router(api)
