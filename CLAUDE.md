# dgu-study

동국대 과목·교수별 시험 공부 웹 서비스 (공개SW프로젝트 D팀). 기능 명세는 `docs/SPEC.md`, DB는 `docs/DB.md`.

## 명령
- 백엔드 (`backend/`): `uv run uvicorn app.main:app --reload --port 8000` / 테스트 `uv run pytest -q` / 검사 `uv run ruff check . && uv run ruff format .`
- 프론트 (`frontend/`): `pnpm dev` / 검사 `pnpm typecheck && pnpm lint && pnpm build`
- 백엔드 API를 바꾸면 `frontend`에서 `pnpm gen:api`를 실행해 `src/api/schema.d.ts`를 다시 만든다. 이 파일은 직접 고치지 않는다.
- 작업을 마치기 전에 위 테스트·검사를 실제로 돌리고 결과를 보여 준다.

## 구조 규칙
- 기능은 `backend/app/features/<기능>/router.py`와 `frontend/src/features/<기능>/`에 같은 이름으로 둔다. 새 라우터는 `app/main.py`, 새 화면은 `src/App.tsx`에 한 줄 등록한다.
- 로그인 사용자는 백엔드에서 `CurrentUser`(get_current_user), 프론트에서 `useAuth()`로만 얻는다.
- 사용자에 딸린 데이터는 `user_id`로 연결한다.
- 프론트의 백엔드 호출은 `src/api/client.ts`의 `api` + `unwrap`만 쓴다.
- LLM 호출은 `backend/app/services/llm.py`만 거친다(아직 미연결).
- 테이블을 바꾸면 `app/models.py` 수정 → `uv run alembic revision --autogenerate -m "설명"` → 생성 파일 확인 → `uv run alembic upgrade head`. 만들기 전에 main을 먼저 받는다.

## 주의
- `data/raw/`(교안 PDF)와 `backend/.env`는 git에 올리지 않는다. `.env`는 읽지도 않는다.
- pyBKT는 `numpy<2`, `scikit-learn<1.7`에서만 동작한다. 버전을 올리지 않는다.
- openapi-typescript는 TypeScript 7과 호환되지 않아 `pnpm gen:api`가 `pnpm dlx`로 TypeScript 5를 따로 쓴다.
- WSL에서 `/mnt/c` 폴더로 개발하면 Vite 파일 감지에 polling이 필요하다(설정되어 있음).
- 테스트는 메모리 SQLite를 쓴다. Postgres 전용 기능을 쓰면 테스트도 확인한다.
