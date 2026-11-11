"""샘플 데이터(data/seed/*.json)를 DB에 넣는다. 여러 번 실행해도 중복으로 들어가지 않는다.

실행 (backend 폴더에서):
    uv run python scripts/seed.py            # DB에 넣기
    uv run python scripts/seed.py --check    # DB는 건드리지 않고 근거 문장만 검사

교안 PDF(data/raw/<json 이름>/)가 있으면 자료로 등록하고, 문제의 근거 문장이 몇 쪽에 있는지 찾아
연결한다. 근거 문장을 원문에서 못 찾으면 실패한다. PDF가 없으면 근거 쪽수 없이 문제만 넣는다.
"""

import json
import re
import sys
from pathlib import Path

from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import engine  # noqa: E402
from app.features.materials.pdf import extract_pages  # noqa: E402
from app.features.materials.versioning import material_title, next_seq, parse_week  # noqa: E402
from app.models import (  # noqa: E402
    Chapter,
    Concept,
    Course,
    Material,
    MisconceptionProbe,
    Problem,
    ProblemConcept,
    Professor,
    Subject,
)

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "data" / "seed"
RAW_DIR = ROOT / "data" / "raw"


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def find_page(pages: list[str], evidence: str) -> int | None:
    """근거 문장이 들어 있는 쪽 번호(1부터). 공백 차이는 무시한다."""
    target = _squash(evidence)
    for i, page in enumerate(pages, 1):
        if target in _squash(page):
            return i
    return None


def load_pdfs(name: str, seed: dict) -> dict[str, list[str]]:
    folder = RAW_DIR / name
    out = {}
    for m in seed["materials"]:
        path = folder / m["file"]
        if path.exists():
            out[m["file"]] = extract_pages(path.read_bytes())
    return out


def check(seed: dict, pdfs: dict[str, list[str]]) -> list[str]:
    errors = []
    for ch in seed["chapters"]:
        names = set(ch["concepts"])
        for p in ch["problems"]:
            label = f"{ch['title']} / {p['question'][:30]}"
            if not 0 <= p["answer"] < len(p["choices"]):
                errors.append(f"{label}: 정답 번호가 보기 범위를 벗어남")
            if len(set(p["choices"])) != len(p["choices"]):
                errors.append(f"{label}: 보기가 중복됨")
            if unknown := set(p["concepts"]) - names:
                errors.append(f"{label}: 챕터에 없는 개념 {unknown}")
            seen_wrong_choices: set[int] = set()
            for probe in p.get("misconception_probes", []):
                wrong = probe["wrong_choice_index"]
                if wrong in seen_wrong_choices or not 0 <= wrong < len(p["choices"]):
                    errors.append(f"{label}: 확인 문제의 오답 보기 번호가 중복되거나 범위를 벗어남")
                if wrong == p["answer"]:
                    errors.append(f"{label}: 정답 보기에는 오개념 확인 문제를 붙일 수 없음")
                seen_wrong_choices.add(wrong)
                if len(probe["choices"]) < 2 or len(set(probe["choices"])) != len(
                    probe["choices"]
                ):
                    errors.append(f"{label}: 확인 문제의 보기는 서로 다른 값 2개 이상이어야 함")
                if not 0 <= probe["answer"] < len(probe["choices"]):
                    errors.append(f"{label}: 확인 문제의 정답 번호가 보기 범위를 벗어남")
                if not all(
                    probe[field].strip() for field in ("hypothesis", "question", "explanation")
                ):
                    errors.append(f"{label}: 오개념 가설·문제·해설을 모두 입력해야 함")
            pages = pdfs.get(ch["material"])
            if pages is not None and find_page(pages, p["evidence"]) is None:
                errors.append(f"{label}: 근거 문장을 {ch['material']}에서 못 찾음")
    return errors


def get_or_create(session: Session, model, defaults: dict | None = None, **where):
    obj = session.exec(select(model).filter_by(**where)).first()
    if obj is None:
        obj = model(**where, **(defaults or {}))
        session.add(obj)
        session.flush()
    return obj


def seed_one(session: Session, seed: dict, pdfs: dict[str, list[str]]) -> dict[str, int]:
    subject = get_or_create(
        session, Subject, {"code": seed["subject"].get("code")}, name=seed["subject"]["name"]
    )
    professor = get_or_create(session, Professor, name=seed["professor"]["name"])
    course = get_or_create(
        session,
        Course,
        {"info": seed["course"]["info"], "exam_info": seed["course"]["exam_info"]},
        subject_id=subject.id,
        professor_id=professor.id,
    )

    materials: dict[str, Material] = {}
    for m in seed["materials"]:
        if m["file"] not in pdfs:
            continue
        pages = pdfs[m["file"]]
        materials[m["file"]] = get_or_create(
            session,
            Material,
            {"kind": "lecture", "title": m["title"], "page_count": len(pages), "pages": pages},
            course_id=course.id,
            filename=m["file"],
        )
        material = materials[m["file"]]
        if material.seq is None:  # 업로드와 같은 이름 규칙: '과목명 교안 n'
            material.week = parse_week(m["title"], m["file"])
            material.seq = next_seq(session, course.id, "lecture")
            material.title = material_title(subject.name, "lecture", material.seq)
            session.add(material)
            session.flush()

    added = 0
    for ch in seed["chapters"]:
        material = materials.get(ch["material"])
        chapter = get_or_create(
            session,
            Chapter,
            {"title": ch["title"], "material_id": material.id if material else None},
            course_id=course.id,
            order=ch["order"],
        )
        concepts = {
            name: get_or_create(session, Concept, chapter_id=chapter.id, name=name)
            for name in ch["concepts"]
        }
        for p in ch["problems"]:
            exists = session.exec(
                select(Problem).where(
                    Problem.chapter_id == chapter.id, Problem.question == p["question"]
                )
            ).first()
            if exists:
                problem = exists
                if problem.choices != p["choices"] or problem.answer_index != p["answer"]:
                    raise ValueError(f"기존 문제의 보기 또는 정답이 시드와 다릅니다: {p['question']}")
            else:
                problem = Problem(
                    chapter_id=chapter.id,
                    question=p["question"],
                    choices=p["choices"],
                    answer_index=p["answer"],
                    explanation=p["explanation"],
                    evidence=p["evidence"],
                    source_material_id=material.id if material else None,
                    source_page=find_page(material.pages, p["evidence"]) if material else None,
                    origin="sample",
                )
                session.add(problem)
                session.flush()
                for name in p["concepts"]:
                    session.add(ProblemConcept(problem_id=problem.id, concept_id=concepts[name].id))
                added += 1
            for probe in p.get("misconception_probes", []):
                wrong = probe["wrong_choice_index"]
                existing_probe = session.exec(
                    select(MisconceptionProbe).where(
                        MisconceptionProbe.problem_id == problem.id,
                        MisconceptionProbe.wrong_choice_index == wrong,
                    )
                ).first()
                if existing_probe is None:
                    session.add(
                        MisconceptionProbe(
                            problem_id=problem.id,
                            wrong_choice_index=wrong,
                            hypothesis=probe["hypothesis"],
                            question=probe["question"],
                            choices=probe["choices"],
                            answer_index=probe["answer"],
                            explanation=probe["explanation"],
                            evidence=p["evidence"],
                            source_material_id=problem.source_material_id,
                            source_page=problem.source_page,
                        )
                    )
    return {"course_id": course.id, "materials": len(materials), "problems_added": added}


def main() -> None:
    only_check = "--check" in sys.argv
    files = sorted(SEED_DIR.glob("*.json"))
    failed = False
    for f in files:
        seed = json.loads(f.read_text(encoding="utf-8"))
        pdfs = load_pdfs(f.stem, seed)
        total = sum(len(c["problems"]) for c in seed["chapters"])
        print(f"[{f.name}] 문제 {total}개, 교안 PDF {len(pdfs)}/{len(seed['materials'])}개 찾음")
        if errors := check(seed, pdfs):
            failed = True
            print("\n".join("  오류: " + e for e in errors))
            continue
        if only_check:
            print("  검사 통과")
            continue
        with Session(engine) as session:
            result = seed_one(session, seed, pdfs)
            session.commit()
        print(f"  넣음: {result}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
