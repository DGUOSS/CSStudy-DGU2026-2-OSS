# dgu-study

동국대 과목·교수별 시험 공부 웹 서비스 (공개SW프로젝트 D팀)

과목 → 교수 → 강좌 페이지에서 그 교수님 교안으로 만든 문제를 풀고, 개념별 숙련도를 확인한다. 기능은 [docs/SPEC.md](docs/SPEC.md), DB는 [docs/DB.md](docs/DB.md).

## 스택
- 백엔드: Python 3.12, FastAPI, SQLModel, Alembic, pyBKT, pypdf
- 프론트: React, Vite, TypeScript, Tailwind, shadcn/ui 형식 부품, TanStack Query, openapi-fetch
- DB: Neon Postgres / 배포: 프론트 Vercel, 백엔드 Render (설정 파일만 준비됨)

## 필요한 것
Git, [uv](https://docs.astral.sh/uv/), Node LTS, pnpm. 윈도우·WSL 모두 된다.

## 실행
```bash
# 1. 백엔드
cd backend
cp ../.env.example .env        # DATABASE_URL 등 채우기 (팀 채팅방에서 받기)
uv sync
uv run alembic upgrade head    # 테이블 만들기 (이미 있으면 그대로)
uv run python scripts/seed.py  # 샘플 데이터 (한 번만, 다시 해도 중복 없음)
uv run uvicorn app.main:app --reload --port 8000

# 2. 프론트 (새 터미널)
cd frontend
pnpm install
pnpm dev                       # http://localhost:5173
```
교안 PDF는 git에 올리지 않는다. 있으면 `data/raw/basic-programming-kang/`에 넣고 시드를 실행해야 문제 해설에 교안 쪽수가 붙는다.

## 확인
```bash
cd backend && uv run pytest -q && uv run ruff check .
cd frontend && pnpm typecheck && pnpm lint && pnpm build
```
PR을 올리면 GitHub Actions가 같은 검사를 돌린다.

## 작업 방식
- `feat/기능명` 브랜치 → PR → 한 명 확인 후 main에 합친다.
- 백엔드 API를 바꾸면 `frontend`에서 `pnpm gen:api`로 프론트 타입을 다시 만든다.
- AI 코딩 도구 공통 규칙은 [CLAUDE.md](CLAUDE.md).

## 배포 (아직 안 함)
1. Render → New → Blueprint → 이 레포. `DATABASE_URL`, `DATABASE_URL_UNPOOLED`를 넣는다. (`render.yaml`)
2. Vercel → 새 프로젝트 → Root Directory `frontend`. `/api`는 Render 주소로 넘어간다. (`frontend/vercel.json`)
3. Render 서비스 이름이 `dgu-study-api`가 아니면 `frontend/vercel.json`의 주소를 바꾼다.
