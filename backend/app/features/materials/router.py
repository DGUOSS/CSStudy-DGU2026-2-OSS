"""강좌 자료(교안·기출·시험 정보) 업로드와 조회. 자료는 개인이 아니라 강좌 공용이다."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import select

from app.core.config import settings
from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.courses.router import get_course_or_404
from app.features.materials.pdf import PdfError, extract_pages
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
    )


@router.get("/courses/{course_id}/materials")
def list_materials(course_id: int, session: SessionDep) -> list[MaterialOut]:
    get_course_or_404(session, course_id)
    rows = session.exec(
        select(Material).where(Material.course_id == course_id).order_by(Material.created_at)
    ).all()
    return [_out(session, m) for m in rows]


@router.post("/courses/{course_id}/materials", status_code=status.HTTP_201_CREATED)
async def upload_material(
    course_id: int,
    session: SessionDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    kind: Annotated[Kind, Form()],
    title: Annotated[str, Form(min_length=1, max_length=200)],
) -> MaterialOut:
    get_course_or_404(session, course_id)
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PDF 파일만 올릴 수 있습니다")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"{settings.max_upload_mb}MB 이하만 올릴 수 있습니다"
        )
    try:
        pages = extract_pages(data)
    except PdfError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None
    material = Material(
        course_id=course_id,
        uploader_id=user.id,
        kind=kind,
        title=title.strip(),
        filename=filename,
        page_count=len(pages),
        pages=pages,
    )
    session.add(material)
    session.commit()
    session.refresh(material)
    return _out(session, material)


@router.get("/materials/{material_id}/pages/{page}")
def get_material_page(material_id: int, page: int, session: SessionDep) -> MaterialPageOut:
    """문제 해설의 '근거 쪽' 링크에서 쓴다. page는 1부터."""
    m = session.get(Material, material_id)
    if m is None or not 1 <= page <= m.page_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "자료나 쪽이 없습니다")
    return MaterialPageOut(material_id=m.id, page=page, text=m.pages[page - 1])
