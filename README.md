# CSStudy-DGU2026-2-OSS

동국대학교 2026-2 공개SW 프로젝트: 학습 상태를 반영하는 주간 학습 플래너

자료와 배운 범위를 등록하고 학습·문제 풀이 기록을 바탕으로 복습과 주간 계획을 지원합니다.

## 백엔드 실행

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

macOS/Linux에서는 `python3 -m venv .venv`로 만들고 위 Python 경로 대신
`.venv/bin/python`을 사용합니다. 서버 종료는 `Ctrl+C`입니다.

- 실행 확인: http://127.0.0.1:8000/health → `{"status":"ok"}`
- API 문서: http://127.0.0.1:8000/docs

현재는 DB나 API 키 없이 실행됩니다. `.env.example`은 이후 DB·설정 연결을 위한 예시이며,
지금 서버가 `.env`를 자동으로 읽지는 않습니다.
`pyproject.toml`은 직접 의존성 범위, `requirements.lock.txt`는 실행 검증한 의존성 버전입니다.

## 폴더 구조

```text
backend/app/
  main.py       # FastAPI 시작점
  api/          # API
  schemas/      # 요청·응답 형식
  models/       # DB 모델
  db/           # DB 연결
  services/     # 기능 처리·연결
  ai/           # 자료 처리·문제 생성
  scheduling/   # 학습 상태·일정 계산
backend/tests/  # 테스트
frontend/       # 웹 화면
docs/           # 공통 설계와 API 합의
```

## 협업

각 기능은 작업 브랜치에서 개발한 뒤 PR로 공유합니다. AI·계산 담당자는 모듈의
입출력 예시를 함께 제공하고, 백엔드 담당자와 서버 연결을 확인합니다.

- [구조와 역할](docs/architecture.md)
- [API 계약과 다음 개발 범위](docs/api-contract.md)

`.env`, API 키, 업로드한 강의자료는 커밋하지 않습니다.
프로젝트 공개 라이선스는 팀에서 별도로 결정합니다.

## just test
