"""테스트는 실제 DB(Neon) 대신 메모리 SQLite를 쓴다."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.db import get_session
from app.main import app
from app.models import Chapter, Concept, Course, Problem, ProblemConcept, Professor, Subject


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def login(client):
    """가입 후 로그인 쿠키가 든 client를 돌려준다."""

    def _login(email: str = "a@dgu.ac.kr", name: str = "민제"):
        r = client.post(
            "/api/v1/auth/signup", json={"email": email, "name": name, "password": "password123"}
        )
        assert r.status_code == 201, r.text
        return client

    return _login


@pytest.fixture
def course_with_problems(session):
    """챕터 1개, 개념 2개(A, B), 문제 3개(A / B / A+B)."""
    subject = Subject(name="기초프로그래밍")
    prof = Professor(name="강동현")
    session.add_all([subject, prof])
    session.flush()
    course = Course(subject_id=subject.id, professor_id=prof.id)
    session.add(course)
    session.flush()
    ch = Chapter(course_id=course.id, order=1, title="포인터")
    session.add(ch)
    session.flush()
    a, b = Concept(chapter_id=ch.id, name="A"), Concept(chapter_id=ch.id, name="B")
    session.add_all([a, b])
    session.flush()
    problems = []
    for concepts in ([a], [b], [a, b]):
        p = Problem(
            chapter_id=ch.id,
            question="q",
            choices=["1", "2", "3", "4"],
            answer_index=1,
            explanation="e",
        )
        session.add(p)
        session.flush()
        for c in concepts:
            session.add(ProblemConcept(problem_id=p.id, concept_id=c.id))
        problems.append(p)
    session.commit()
    return {"course": course, "chapter": ch, "a": a, "b": b, "problems": problems}


def make_pdf(pages: list[str]) -> bytes:
    """글자가 든 최소 PDF를 만든다 (ASCII만)."""
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        None,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    kids = []
    for text in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode()}\nendstream")
        content_id = len(objs)
        objs.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        )
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out
