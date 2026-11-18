from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.features.courses.router import get_course_or_404
from app.features.enrollments.service import require_course_access, term_label
from app.models import CourseReview, Enrollment

router = APIRouter(tags=["reviews"])


class ReviewBody(BaseModel):
    recommendation: int = Field(ge=1, le=5)
    difficulty: int = Field(ge=1, le=5)
    workload: int = Field(ge=1, le=5)
    content: str = Field(min_length=10, max_length=3000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("후기는 공백을 제외한 앞뒤 정리 후 10자 이상 입력해 주세요")
        return value


class ReviewCreate(ReviewBody):
    enrollment_id: int


class ReviewOut(ReviewBody):
    id: int
    year: str
    sem_cd: str
    term: str
    is_mine: bool
    created_at: datetime


class ReviewTerm(BaseModel):
    enrollment_id: int
    term: str
    review_id: int | None


def output(review: CourseReview, user_id: int) -> ReviewOut:
    return ReviewOut(
        **review.model_dump(exclude={"user_id", "course_id", "enrollment_id"}),
        term=term_label(review.year, review.sem_cd),
        is_mine=review.user_id == user_id,
    )


def enrollment(session, user_id: int, course_id: int, enrollment_id: int) -> Enrollment:
    e = session.get(Enrollment, enrollment_id)
    if e is None or e.user_id != user_id or e.course_id != course_id:
        raise HTTPException(403, "본인의 수강 기록이 연결된 강좌에만 후기를 작성할 수 있습니다")
    return e


@router.get("/courses/{course_id}/reviews/terms")
def review_terms(course_id: int, session: SessionDep, user: CurrentUser) -> list[ReviewTerm]:
    course = get_course_or_404(session, course_id)
    require_course_access(session, user, course)
    records = session.exec(
        select(Enrollment)
        .where(Enrollment.user_id == user.id, Enrollment.course_id == course_id)
        .order_by(Enrollment.year.desc(), Enrollment.sem_cd.desc())
    ).all()
    reviews = session.exec(
        select(CourseReview).where(
            CourseReview.user_id == user.id, CourseReview.course_id == course_id
        )
    ).all()
    existing_id = reviews[0].id if reviews else None
    seen = set()
    result = []
    for e in records:
        key = (e.year, e.sem_cd)
        if key not in seen:
            seen.add(key)
            result.append(
                ReviewTerm(enrollment_id=e.id, term=term_label(*key), review_id=existing_id)
            )
    return result


@router.get("/courses/{course_id}/reviews")
def list_reviews(
    course_id: int,
    session: SessionDep,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
) -> list[ReviewOut]:
    require_course_access(session, user, get_course_or_404(session, course_id))
    rows = session.exec(
        select(CourseReview)
        .where(CourseReview.course_id == course_id, CourseReview.is_deleted == False)  # noqa: E712
        .order_by(CourseReview.created_at.desc(), CourseReview.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [output(r, user.id) for r in rows]


@router.post("/courses/{course_id}/reviews", status_code=201)
def create_review(
    course_id: int, body: ReviewCreate, session: SessionDep, user: CurrentUser
) -> ReviewOut:
    get_course_or_404(session, course_id)
    e = enrollment(session, user.id, course_id, body.enrollment_id)
    review = CourseReview(
        **body.model_dump(),
        user_id=user.id,
        course_id=course_id,
        year=e.year,
        sem_cd=e.sem_cd,
    )
    session.add(review)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            409, "같은 과목·교수의 강좌에는 학기와 관계없이 한 번만 작성할 수 있습니다"
        ) from None
    session.refresh(review)
    return output(review, user.id)


def owned_review(session, user_id: int, review_id: int) -> CourseReview:
    r = session.get(CourseReview, review_id)
    if r is None or r.user_id != user_id or r.is_deleted:
        raise HTTPException(404, "내 후기를 찾을 수 없습니다")
    return r


@router.delete("/reviews/{review_id}", status_code=204)
def delete_review(review_id: int, session: SessionDep, user: CurrentUser) -> Response:
    # 연결이 바뀐 뒤에도 본인이 쓴 후기는 삭제할 수 있다.
    r = owned_review(session, user.id, review_id)
    # 삭제 후 재작성으로 수정 제한을 우회하지 않도록 작성 이력은 유지한다.
    r.is_deleted = True
    r.content = ""
    session.add(r)
    session.commit()
    return Response(status_code=204)
