# API 계약

## 구현 완료

### GET /health

인증 없이 API 프로세스의 실행 상태를 확인합니다. DB 상태는 검사하지 않습니다.

응답: `200 OK`

```json
{"status": "ok"}
```

실행 중인 API 명세: `/docs`, `/openapi.json`

## 다음 개발 범위 — 아직 구현되지 않은 초안

| 기능 | API 후보 |
| --- | --- |
| 과목 생성·조회 | `POST /courses`, `GET /courses` |
| 자료 업로드 | `POST /courses/{course_id}/materials` |
| 자료 정보·처리 상태 | `GET /materials/{material_id}` |
| 배운 범위 등록 | `POST /study-ranges` |
| 태스크 조회·수정 | `GET /tasks`, `PATCH /tasks/{task_id}` |

프론트·AI·계산 담당과 필드, 오류 응답, 식별자 형식, 날짜·시간 기준을 합의한 뒤 구현합니다.
배운 범위에는 자료 ID, 시작·끝 페이지, 실제 배운 날짜가 필요합니다.
PDF의 물리 페이지 번호와 책에 인쇄된 쪽 번호의 차이도 입력 규칙에서 정합니다.

후속 API: 인증, 과제·시험, 퀴즈 조회·제출, 복습 완료, 주간 계획 생성·조회·적용,
일정 이동·고정, 쉬는 날 설정.
