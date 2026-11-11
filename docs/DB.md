# DB 구조

정의는 `backend/app/models.py`. DB는 Neon Postgres(싱가포르), 변경 이력은 Alembic(`backend/migrations/`).

```
subjects ─< courses >─ professors        과목 + 교수 = 강좌 (한 쌍은 하나만)
courses ─< materials                      교안·기출·시험 정보, 쪽별 텍스트(JSON)
courses ─< chapters ─< concepts
chapters ─< problems >─< concepts         problem_concepts로 연결 (한 문제에 개념 여러 개)
problems ─< misconception_probes          오답 보기별 오개념 가설·확인 문제
users ─< attempts >─ problems             풀이 기록. 숙련도는 이 기록으로 계산한다 (따로 저장하지 않음)
users ─< course_requests ─ courses        과목·강좌 추가 요청, 관리자가 승인하면 강좌와 연결
materials ─ materials(replaced_by)        자료의 판 관리: 옛 판이 새 판을 가리킨다
users ─< user_subjects >─ subjects        내 과목(수강 중/수강함). 이 과목의 강좌에만 들어간다
users ─< material_votes >─ materials      족보 좋아요/싫어요
users ─< exam_selections >─ materials     문제 풀기 전에 고른 족보(문제 생성 때 참고)
```

| 테이블 | 주요 칸 |
|---|---|
| users | email(고유), name, password_hash(argon2), role(user/admin) |
| subjects | name(고유), code(학수번호) |
| professors | name, department |
| courses | subject_id, professor_id, info, exam_info, created_by |
| materials | course_id, uploader_id, kind(lecture/exam/note), title, filename, page_count, pages(JSON), status, week(표시용), version, seq(강좌·종류별 번호, 제목 '과목명 종류 번호'), replaced_by(새 판 id, 최신판은 NULL) |
| course_requests | requester_id, subject_name, subject_code, professor_name, semester, note, material_title/filename/pages(JSON, 승인 전까지만), status(pending/approved/rejected), reject_reason, reviewed_by, reviewed_at, course_id |
| chapters | course_id, order, title, material_id |
| concepts | chapter_id, name |
| problems | chapter_id, question, choices(JSON), answer_index(0부터), explanation, evidence, source_material_id, source_page, origin(sample/llm/exam) |
| problem_concepts | problem_id, concept_id |
| misconception_probes | problem_id + wrong_choice_index(고유), hypothesis, question, choices(JSON), answer_index, explanation, evidence, source_material_id, source_page, status(draft/approved), reviewed_by, reviewed_at |
| attempts | user_id, problem_id, chosen_index, correct, created_at |
| user_subjects | (user_id, subject_id) 기본키, status(current/taken), semester, source(manual/ndrims) |
| material_votes | (user_id, material_id) 기본키, value(1/-1) |
| exam_selections | (user_id, material_id) 기본키, course_id |

## 테이블을 바꿀 때
1. `git pull`로 main을 먼저 받는다 (두 사람이 동시에 바꾸면 변경 이력이 갈라진다).
2. `app/models.py`를 고친다.
3. `uv run alembic revision --autogenerate -m "설명"` → `migrations/versions/`에 생긴 파일을 열어 확인한다.
4. `uv run alembic upgrade head`
5. 모델 파일과 마이그레이션 파일을 같은 커밋에 올린다.

## 처음 세팅
```bash
cd backend
uv run alembic upgrade head
uv run python scripts/seed.py      # 교안 PDF가 data/raw/basic-programming-kang/에 있으면 근거 쪽수까지 연결
```
