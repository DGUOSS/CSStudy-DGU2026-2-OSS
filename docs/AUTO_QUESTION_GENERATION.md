# 자동 문제 보충

## 동작

퀴즈 문제 조회(`GET .../next`)와 답안 제출 뒤, 그 사용자가 강좌 전체에서 아직 풀지 않은 객관식이 **2개 이하**면 백그라운드에서 5문항 생성을 시도한다. 새 문제는 다음 조회부터 보인다.

대상 챕터는 안 푼 객관식이 가장 적은 챕터 중 **챕터에 연결된 승인 교안(`chapter.material_id`)과 개념이 있는 것**이다. 연결된 교안이 없는 챕터는 건너뛴다(다른 교안으로 만들면 챕터 개념과 맞지 않는 문제가 생긴다).

## 생성기와의 관계

`question-ai/`(qgen)는 생성기 담당 코드이고 backend는 **고치지 않고 가져다 쓴다**. 사이트에 필요한 것은 전부 `backend/app/features/problems/generation.py`에서 감싼다.

| 필요한 것 | 처리 |
|---|---|
| 해설·근거·개념 칸 | `qgen.schemas.Question`을 상속한 `SiteQuestion` |
| 개념 목록 등 추가 지시 | `qgen.llm.render_prompt`로 원래 프롬프트를 만든 뒤 뒤에 덧붙임 |
| 모델 호출 | `qgen.agents` 대신 같은 순서(출제 → 규칙검사 → 블라인드 풀이 → 검토 → 수정/재출제, `qgen.pipeline`과 같음)를 사이트 Claude 호출(`services/llm._parse`)로 실행 |
| 검사 | `qgen.checks.run` 뒤에 사이트 검사 추가 |

사이트 검사:
- 근거(evidence): 공백·문장부호를 빼고 비교해 검색된 교안 쪽에 그대로 있어야 하고, 그 쪽이 `sources`에 있어야 한다. 정규화 후 8자 미만이면 탈락.
- 개념(concepts): 챕터 개념 목록의 이름과 **글자 그대로** 같아야 한다(1개 이상, 중복 없음). 맞지 않으면 수정 지시와 함께 다시 출제하고, 끝까지 맞지 않으면 저장하지 않는다. 첫 번째 개념에 붙이는 대체 동작은 없다.
- 정답은 번호 하나.

수정·재출제 횟수(2회/1회)와 검색 개수(4)는 `question-ai/config.yaml`의 pipeline 값과 같게 상수로 둔다.

## 설치

qgen은 커밋을 고정한 git 의존성으로 설치한다(`backend/pyproject.toml`의 `[tool.uv.sources]`). Render는 Root Directory(`backend`) 밖 파일을 쓸 수 없어 `../question-ai` 경로 의존성은 배포에서 동작하지 않는다. 생성기를 갱신하려면 `rev`를 새 커밋으로 바꾸고 `uv lock`을 실행한다.

**현재 제약:** `qgen.llm`은 import할 때 `config.yaml`과 `prompts/`를 패키지 밖 경로(`src/`의 상위 폴더)에서 읽는다. git 설치본에는 이 파일들이 없어 import가 실패하므로 `render_prompt`를 쓰는 생성이 동작하지 않는다(`qgen.checks`·`schemas`·`ingest`는 동작). question-ai 쪽 수정이 들어온 뒤 `rev`를 올려야 한다.

## 비용 상한(강좌별)

- 생성 중이면 새로 시작하지 않는다.
- 저장 0개로 끝나거나 예외가 나면 1시간 쉰다.
- 성공해도 다음 시도까지 10분.
- 하루(UTC) 최대 5번 시작 → 하루 최대 25문항.

기록은 서버 메모리에 있다. 재시작하면 초기화되고, 서버를 여러 대로 늘리면 공유되지 않는다.

## 배포

Render 백엔드에 `ANTHROPIC_API_KEY`를 설정한다. 없으면 자동 생성이 꺼진다. 모델은 `QGEN_MODEL`(기본 `claude-haiku-5-5`).
