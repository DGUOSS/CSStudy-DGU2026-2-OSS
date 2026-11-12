"""강좌 자료(교안·기출·시험 정보) 업로드와 조회. 자료는 개인이 아니라 강좌 공용이다."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlmodel import select

from app.core.config import settings
from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.courses.router import get_course_or_404
from app.features.enrollments.service import require_course_access
from app.features.materials.pdf import PdfError, extract_pages
from app.features.materials.versioning import Action, add_material
from app.models import Material, User

router = APIRouter(tags=["materials"])

Kind = Literal["lecture", "exam", "note"]


class MaterialOut(BaseModel):
    id: int
    course_id: int
    kind: str
    title: str
    filename: str
    page_count: int
    uploader_name: str | None
    created_at: datetime
    week: int | None = None
    version: int = 1
    replaced_by: int | None = None


class UploadOut(MaterialOut):
    # new: 새 자료 / updated: 기존 자료의 새 판(옛 판은 목록에서 숨김) / duplicate: 같은 내용이 이미 있어 등록 안 함
    action: Action
    relinked_problems: int = 0
    # 쪽 비교 결과: 기존 교안과 같은 쪽 / 수정된 쪽 / 새 내용 쪽 수, 이번에 대체된 기존 자료 id
    pages_same: int = 0
    pages_modified: int = 0
    pages_new: int = 0
    replaced_ids: list[int] = []


class MaterialPageOut(BaseModel):
    material_id: int
    page: int
    text: str


def _out(session: SessionDep, m: Material) -> MaterialOut:
    uploader = session.get(User, m.uploader_id) if m.uploader_id else None
    return MaterialOut(
        id=m.id,
        course_id=m.course_id,
        kind=m.kind,
        title=m.title,
        filename=m.filename,
        page_count=m.page_count,
        uploader_name=uploader.name if uploader else None,
        created_at=m.created_at,
        week=m.week,
        version=m.version,
        replaced_by=m.replaced_by,
    )


@router.get("/courses/{course_id}/materials")
def list_materials(
    course_id: int, session: SessionDep, user: CurrentUser, all_versions: bool = False
) -> list[MaterialOut]:
    """기본은 최신판만. all_versions=true면 옛 판까지."""
    require_course_access(session, user, get_course_or_404(session, course_id))
    cond = [Material.course_id == course_id]
    if not all_versions:
        cond.append(Material.replaced_by.is_(None))  # type: ignore[union-attr]
    # 쪽별 본문(pages)은 크기가 커서 목록에서는 읽지 않는다
    rows = session.exec(
        select(
            Material.id,
            Material.course_id,
            Material.kind,
            Material.title,
            Material.filename,
            Material.page_count,
            Material.created_at,
            User.name,
            Material.week,
            Material.version,
            Material.replaced_by,
        )
        .join(User, User.id == Material.uploader_id, isouter=True)
        .where(*cond)
        .order_by(Material.created_at, Material.id)
    ).all()
    return [
        MaterialOut(
            id=r[0],
            course_id=r[1],
            kind=r[2],
            title=r[3],
            filename=r[4],
            page_count=r[5],
            created_at=r[6],
            uploader_name=r[7],
            week=r[8],
            version=r[9],
            replaced_by=r[10],
        )
        for r in rows
    ]


@router.post("/courses/{course_id}/materials", status_code=status.HTTP_201_CREATED)
async def upload_material(
    course_id: int,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    file: Annotated[UploadFile, File()],
    kind: Annotated[Kind, Form()],
    title: Annotated[str | None, Form(max_length=200)] = None,
) -> UploadOut:
    """같은 내용이면 등록하지 않고(200, duplicate), 같은 자료의 수정본이면 새 판으로 대체한다(updated).

    제목은 '과목명 종류 번호'로 자동으로 붙는다. title은 주차를 읽는 데만 쓴다(선택).
    """
    require_course_access(session, user, get_course_or_404(session, course_id))
    filename, pages = await read_pdf(file)
    material, action, relinked, diff = add_material(
        session,
        course_id=course_id,
        uploader_id=user.id,
        kind=kind,
        title=(title or "").strip() or filename,
        filename=filename,
        pages=pages,
    )
    session.commit()
    session.refresh(material)
    if action == "duplicate":
        response.status_code = status.HTTP_200_OK
    return UploadOut(
        **_out(session, material).model_dump(),
        action=action,
        relinked_problems=relinked,
        pages_same=diff.same,
        pages_modified=diff.modified,
        pages_new=diff.new,
        replaced_ids=[] if action == "duplicate" else diff.replaced,
    )


async def read_pdf(file: UploadFile) -> tuple[str, list[str]]:
    """올린 파일을 검사하고 쪽별 텍스트를 뽑는다. 과목 추가 요청에서도 쓴다."""
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PDF 파일만 올릴 수 있습니다")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"{settings.max_upload_mb}MB 이하만 올릴 수 있습니다"
        )
    try:
        return filename, extract_pages(data)
    except PdfError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None


@router.get("/materials/{material_id}/pages/{page}")
def get_material_page(
    material_id: int, page: int, session: SessionDep, user: CurrentUser
) -> MaterialPageOut:
    """문제 해설의 '근거 쪽' 링크에서 쓴다. page는 1부터."""
    m = session.get(Material, material_id)
    if m is None or not 1 <= page <= m.page_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "자료나 쪽이 없습니다")
    require_course_access(session, user, get_course_or_404(session, m.course_id))
    return MaterialPageOut(material_id=m.id, page=page, text=m.pages[page - 1])
