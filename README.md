# dgu-study

동국대 과목·교수별 시험 공부 웹 서비스 (공개SW프로젝트 D팀)

## 실행
```bash
# 백엔드 (Python 3.12, uv 필요)
cd backend
cp ../.env.example .env   # DATABASE_URL 채우기
uv sync
uv run uvicorn app.main:app --reload --port 8000

# 프론트 (Node LTS, pnpm 필요)
cd frontend
pnpm install
pnpm dev                  # http://localhost:5173
```
