# 구조와 역할

## 현재 범위

사용자가 PDF와 실제 배운 범위를 등록하면 학습·복습을 지원하고,
과제·시험을 반영해 주간 부담을 분산하는 웹 서비스입니다.
eClass 자동 수집과 확장 프로그램은 현재 구현 범위에서 제외합니다.

## 구성

웹 화면 → FastAPI → PostgreSQL 및 파일 저장소

| 경로 | 책임 |
| --- | --- |
| `backend/app/api` | HTTP 요청과 응답 |
| `backend/app/schemas` | 공통 요청·응답 형식 |
| `backend/app/models`, `db` | DB 모델, 연결, 저장 |
| `backend/app/services` | 기능 흐름과 모듈 연결 |
| `backend/app/ai` | 자료 텍스트 추출, 문제 생성·품질 검사 |
| `backend/app/scheduling` | 부담도, 복습일, 주간 배치·주중 반영 |
| `frontend` | 사용자 화면 |
