"""Prepare an isolated SQLite demo with real local lecture PDFs."""

import json
import os
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seed import RAW_DIR, SEED_DIR, check, load_pdfs, seed_one  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.features.admin.misconception_probes import _validate  # noqa: E402
from app.models import (  # noqa: E402
    Chapter,
    Course,
    MisconceptionProbe,
    Problem,
    User,
    UserSubject,
)

DEMO_DB_URL = "sqlite:///./.venv/demo.db"
ADMIN_EMAIL = "demo-admin@dgu.ac.kr"
STUDENT_EMAIL = "demo-student@dgu.ac.kr"


def main() -> None:
    if (
        os.environ.get("DATABASE_URL") != DEMO_DB_URL
        or os.environ.get("DATABASE_URL_UNPOOLED") != DEMO_DB_URL
    ):
        raise RuntimeError("데모 전용 DB 주소를 설정한 start_demo.ps1에서 실행하세요.")
    path = SEED_DIR / "basic-programming-kang.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    pdfs = load_pdfs(path.stem, data)
    if len(pdfs) != len(data["materials"]):
        raise RuntimeError(f"교안 PDF가 부족합니다: {RAW_DIR / path.stem}")
    if errors := check(data, pdfs):
        raise RuntimeError("교안 검증 실패: " + "; ".join(errors))

    password = secrets.token_urlsafe(12)
    with Session(engine) as session:
        seeded = seed_one(session, data, pdfs)
        session.flush()
        for email, name, role in (
            (ADMIN_EMAIL, "데모 관리자", "admin"),
            (STUDENT_EMAIL, "데모 학생", "user"),
        ):
            user = session.exec(select(User).where(User.email == email)).first()
            if user is None:
                user = User(
                    email=email, name=name, password_hash=hash_password(password), role=role
                )
            else:
                user.password_hash = hash_password(password)
            user.role = role
            session.add(user)
            session.flush()
        course = session.get(Course, seeded["course_id"])
        student = session.exec(select(User).where(User.email == STUDENT_EMAIL)).one()
        if session.get(UserSubject, (student.id, course.subject_id)) is None:
            session.add(UserSubject(user_id=student.id, subject_id=course.subject_id))
        probes = session.exec(select(MisconceptionProbe).order_by(MisconceptionProbe.id)).all()
        target = next((probe for probe in probes if probe.wrong_choice_index == 0), None)
        if target is None:
            raise RuntimeError("데모 확인 문제를 찾을 수 없습니다.")
        _validate(session, target)
        target.status = "approved"
        target.reviewed_by = session.exec(select(User).where(User.email == ADMIN_EMAIL)).one().id
        target.reviewed_at = datetime.now(UTC)
        session.add(target)
        problem = session.get(Problem, target.problem_id)
        chapter = session.get(Chapter, problem.chapter_id)
        course_id, chapter_id, problem_id = course.id, chapter.id, problem.id
        wrong_choice = problem.choices[target.wrong_choice_index]
        session.commit()

    url = (
        f"http://127.0.0.1:5173/courses/{course_id}/chapters/{chapter_id}/quiz"
        f"?problemId={problem_id}"
    )
    info = (
        f"주소: {url}\n"
        f"학생: {STUDENT_EMAIL}\n관리자: {ADMIN_EMAIL}\n"
        f"공통 비밀번호: {password}\n"
        f"데모 오답: {wrong_choice}\n"
        "관리자 검토 화면: http://127.0.0.1:5173/admin/misconception-probes\n"
    )
    (Path(__file__).resolve().parents[1] / ".venv" / "demo-info.txt").write_text(
        info, encoding="utf-8"
    )
    print(info)


if __name__ == "__main__":
    main()
