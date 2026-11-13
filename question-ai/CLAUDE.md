# 출제 경향 기반 문제 생성 멀티에이전트 시스템 — 프로토타입 명세

> 이 파일은 Claude Code가 프로젝트를 구현할 때 따르는 명세다. 구현은 아래 **구현 순서(마일스톤)** 대로 한 단계씩 진행하고, 각 단계가 끝나면 완료 기준을 확인한 뒤 다음 단계로 넘어간다.

## 1. 프로젝트 개요

대학 전공 시험의 **출제 경향(교수 스타일)에 맞는 모의고사**를 생성하는 멀티에이전트 시스템.

- **무엇을 낼지**: 강의자료(PDF)에서 가져온다.
- **어떻게 낼지**: 기출(1~2회)과 사용자가 적은 시험 정보 메모로 만든 **출제 프로필**을 따른다.
- 기출이 매우 적으므로 **학습(파인튜닝)은 하지 않는다**. 기출은 스타일 예시로만 쓴다.
- 핵심 아이디어: **출제자와 풀이자를 서로 다른 모델로 두어 교차 검증**한다.

### 제약 조건
- 개발 환경: 노트북, **RAM 8GB, GPU 없음**
- 기간: 약 3.5주 (프로토타입 + 비교 실험)
- 모든 LLM 호출은 **API**로 한다. 로컬에서는 PDF 파싱, 임베딩 검색, 규칙 기반 체크, 오케스트레이션만 한다.
- 로컬 LLM(Ollama 등)은 사용하지 않는다.

### 범위
| 포함 | 제외 |
|---|---|
| 과목 1~2개 | 파인튜닝 |
| 객관식 / 단답형 / 서술형 / 계산형 | 그림 직접 생성 (기존 그림 "참조"만) |
| LaTeX 수식 | 여러 교수 자동 대응 |
| 비교 실험(ablation) 3종 + 기출 hold-out 평가 | 사용자 계정, DB, 배포 |
| (여유 시) Streamlit 화면 | |

---

## 2. 기술 스택

- Python 3.11+
- LLM 호출: **LiteLLM** (여러 회사 모델을 같은 인터페이스로 호출)
- 스키마 검증: **pydantic v2**
- PDF: **PyMuPDF (fitz)** — 텍스트 추출 + 페이지 이미지 렌더링
- 임베딩: **sentence-transformers** `intfloat/multilingual-e5-small` (CPU, 8GB에서 동작) + numpy 코사인 유사도 (벡터 DB 쓰지 않음)
- 캐시: 디스크 JSON 캐시 (직접 구현, 키 = 요청 해시)
- 설정: `config.yaml` + `.env` (API 키)
- UI(선택): Streamlit
- 테스트: pytest

`requirements.txt`는 위 패키지로 최소한으로 구성한다. torch는 CPU 버전.

---

## 3. 디렉토리 구조

```
qgen/
├── CLAUDE.md
├── config.yaml              # 에이전트별 모델, 루프 횟수, 실험 설정
├── .env.example             # API 키 템플릿 (실제 .env는 git 제외)
├── requirements.txt
├── data/
│   └── <course_id>/
│       ├── lectures/        # 강의자료 PDF
│       ├── past_exams/      # 기출 PDF 또는 이미지 (exam_A.pdf, exam_B.pdf)
│       └── notes.md         # 사용자가 쓴 시험 정보 메모
├── outputs/
│   └── <course_id>/<run_id>/  # 실행 결과 (profile.json, plan.json, exam.json, logs.jsonl, report.md)
├── cache/                   # LLM 응답 캐시
├── src/qgen/
│   ├── schemas.py           # pydantic 모델 전부
│   ├── llm.py               # LiteLLM 래퍼: 캐시, 재시도, JSON 파싱, 토큰 로그
│   ├── ingest/
│   │   ├── pdf_parser.py    # PDF → 페이지 텍스트 / 이미지
│   │   ├── chunker.py       # 페이지 텍스트 → 개념 단위 청크
│   │   └── index.py         # 임베딩 생성, 저장, 검색
│   ├── agents/
│   │   ├── base.py          # Agent 공통 클래스 (프롬프트 로드, 모델 호출, 스키마 검증)
│   │   ├── analyst.py       # 출제 프로필 생성
│   │   ├── planner.py       # 시험 구성 계획
│   │   ├── generator.py     # 문항 생성 / 수정
│   │   ├── solver.py        # 블라인드 풀이
│   │   └── reviewer.py      # 판정 + 피드백
│   ├── checks.py            # 규칙 기반 검사 (LLM 쓰지 않음)
│   ├── pipeline.py          # 전체 오케스트레이션
│   ├── evaluate.py          # 지표 계산, hold-out 비교
│   └── render.py            # exam.json → Markdown(LaTeX 포함) 시험지 / 답안지
├── prompts/                 # 에이전트별 프롬프트 템플릿 (.md, 한국어)
├── scripts/
│   ├── build_index.py       # python scripts/build_index.py --course os
│   ├── make_profile.py
│   ├── generate_exam.py
│   └── run_experiments.py
├── app.py                   # (선택) Streamlit
└── tests/
```

---

## 4. 데이터 스키마 (`schemas.py`)

모든 에이전트 입출력은 아래 pydantic 모델로 검증한다. LLM에게는 JSON으로만 답하게 하고, 파싱/검증 실패 시 에러 메시지를 붙여 최대 2회 재요청한다.

```python
class SourceRef(BaseModel):
    file: str
    page: int

class Chunk(BaseModel):
    chunk_id: str
    course_id: str
    text: str
    source: SourceRef
    has_figure: bool = False
    has_formula: bool = False

class ExamProfile(BaseModel):
    course: str
    professor: str | None = None
    format_ratio: dict[str, float]        # {"객관식":0.2,"단답형":0.3,"서술형":0.4,"계산형":0.1}, 합 = 1
    num_questions: int
    detail_level: Literal["핵심 위주", "중간", "지엽적"]
    difficulty: Literal["쉬움", "보통", "어려움"]
    recurring_patterns: list[str]         # "스케줄링 계산 문제 1개 이상" 등
    phrasing_examples: list[str]          # 기출에서 뽑은 발문 표현
    emphasized_topics: list[str]
    notes: str = ""
    evidence: list[str] = []              # 각 판단의 근거 (기출 몇 번 문제, 메모 어느 줄)

class PlannedItem(BaseModel):
    item_id: str
    qtype: Literal["객관식", "단답형", "서술형", "계산형"]
    topic: str
    bloom_level: Literal["기억", "이해", "적용", "분석", "평가", "창안"]
    difficulty: Literal["쉬움", "보통", "어려움"]
    points: int
    rationale: str                        # 왜 이 문항을 넣었는지 (프로필 근거)

class ExamPlan(BaseModel):
    items: list[PlannedItem]

class Question(BaseModel):
    item_id: str
    qtype: str
    stem: str                             # 문제 본문, 수식은 LaTeX ($...$, $$...$$)
    choices: list[str] | None = None      # 객관식만
    answer: str                           # 정답 (객관식은 번호)
    model_answer: str | None = None       # 서술형/계산형 모범답안
    rubric: list[str] | None = None       # 서술형 채점 기준 (항목별 배점 포함)
    sources: list[SourceRef]              # 근거가 된 강의자료 위치 (필수, 1개 이상)
    figure_ref: SourceRef | None = None   # 그림을 참조하는 경우

class SolverOutput(BaseModel):
    item_id: str
    answer: str
    reasoning: str
    confidence: float                     # 0~1
    is_ambiguous: bool                    # 답이 여러 개이거나 문제가 불명확하다고 판단했는지

class Review(BaseModel):
    item_id: str
    verdict: Literal["pass", "revise", "reject"]
    answer_match: Literal["일치", "부분일치", "불일치"]
    grounded: bool                        # 강의자료 근거로 정답이 지지되는가
    profile_fit: bool                     # 계획된 유형/난이도/스타일에 맞는가
    issues: list[str]
    feedback: str                         # revise일 때 출제자에게 줄 구체적 수정 지시
```

---

## 5. 에이전트 명세

모델은 `config.yaml`에서 에이전트별로 지정한다. 코드에 모델 이름을 하드코딩하지 않는다.

```yaml
# config.yaml 예시 (모델 이름은 사용자가 가진 API에 맞게 바꾼다)
models:
  analyst:   "provider/vision-capable-model"
  planner:   "provider/cheap-model"
  generator: "provider-A/strong-model"
  solver:    "provider-B/model"        # generator와 다른 회사 모델 권장
  reviewer:  "provider/mid-model"
pipeline:
  max_revisions: 2                     # 문항당 수정 최대 횟수
  max_regenerations: 1                 # reject 후 새로 생성 최대 횟수
  retrieval_top_k: 5
  temperature: {generator: 0.8, others: 0.2}
```

| 에이전트 | 입력 | 출력 | 비고 |
|---|---|---|---|
| **Analyst** | 기출(텍스트 또는 페이지 이미지), notes.md | `ExamProfile` | 과목당 1회. 기출 페이지에 수식/그림이 많으면 이미지로 전달. 사용자가 profile.json을 직접 수정할 수 있어야 함 |
| **Planner** | `ExamProfile`, 강의자료 목차/청크 주제 목록 | `ExamPlan` | format_ratio와 num_questions를 정확히 지킬 것. 주제는 강의자료에 실제로 있는 것만 |
| **Generator** | `PlannedItem`, 검색된 강의자료 청크 top-k, 같은 유형 기출 예시 1~2개, `ExamProfile` | `Question` | 기출 문장을 그대로 베끼지 말 것. sources 필수. 수정 모드에서는 이전 문항 + Review.feedback 입력 |
| **Solver** | `Question`에서 **answer/model_answer/rubric 제거한 것** + 관련 강의자료 청크 | `SolverOutput` | 정답을 절대 보지 못하게 할 것 (코드에서 필드를 지워서 전달) |
| **Reviewer** | 원본 `Question`, `SolverOutput`, `PlannedItem`, 근거 청크, `ExamProfile` | `Review` | 서술형은 rubric 기준으로 Solver 답안 채점 후 answer_match 판정 |

### 검색(Retrieval)
- 쿼리 = `PlannedItem.topic` (+ 필요시 bloom_level 설명)
- e5 모델 규칙: 문서는 `"passage: "`, 쿼리는 `"query: "` 접두어
- `detail_level == "지엽적"`이면 top-k를 늘리고, 이미 많이 쓰인 청크는 제외해 세부 내용 위주로 뽑는다.

---

## 6. 파이프라인 (`pipeline.py`)

```
profile = load_or_run(Analyst)              # outputs/.../profile.json 있으면 재사용
plan    = Planner(profile)
for item in plan.items:                     # 문항 단위 독립 처리
    chunks = retrieve(item)
    q = Generator(item, chunks, examples, profile)
    for attempt in range(max_revisions + 1):
        rule_issues = checks.run(q, item)   # 규칙 기반 먼저 (비용 0)
        if rule_issues: q = Generator.revise(q, rule_issues); continue
        s = Solver(strip_answer(q), chunks)
        r = Reviewer(q, s, item, chunks, profile)
        log(item, attempt, q, s, r)
        if r.verdict == "pass": accept(q); break
        if r.verdict == "reject": q = regenerate_or_drop(item); continue
        q = Generator.revise(q, r.feedback)
    else:
        mark_failed(item)                   # 실패 문항도 로그에 남김
render(exam)                                # exam.md (문제지), answers.md (정답·채점기준·근거)
```

### 규칙 기반 검사 (`checks.py`, LLM 미사용)
- 객관식: 선지 개수(기본 5, 프로필 따라), 선지 중복, 정답 번호 범위, "모두 고르시오" 등 형식 일치
- 선지 길이 편차가 지나치게 큰지 (정답만 길면 경고)
- LaTeX 괄호/`$` 짝 맞는지
- sources가 실제 존재하는 파일/페이지인지
- 기출 문항과 임베딩 유사도 > 0.9이면 "베끼기" 경고

---

## 7. 실험 모드 (`run_experiments.py`)

같은 과목, 같은 ExamPlan으로 조건만 바꿔 비교한다. 각 조건 N세트(기본 3) 생성.

| 조건 | 설명 |
|---|---|
| `single` | Generator만 1회 호출, 검증 없음 (베이스라인) |
| `multi_same` | 전체 루프, Solver = Generator와 **같은** 모델 |
| `multi_cross` | 전체 루프, Solver = **다른 회사** 모델 (제안 방법) |
| `multi_no_loop` | Solver/Reviewer로 판정만 하고 수정 루프 없음 |

**최종 품질 판정은 조건과 무관한 고정 평가자 모델**로 한다 (`config.yaml`의 `models.judge`). 생성에 쓴 모델과 겹치지 않게.

### 평가 지표 (`evaluate.py`)
- **정답 오류율**: judge가 강의자료만 보고 풀었을 때 정답과 불일치하는 비율
- **모호성 비율**: judge가 is_ambiguous=True로 판단한 비율
- **근거율**: sources의 청크가 정답을 실제로 지지하는 비율 (judge 판정)
- **프로필 부합도**: 생성 시험의 유형 비율 vs profile.format_ratio의 total variation distance
- **QGEval 7차원**(유창성, 명확성, 간결성, 관련성, 일관성, 답변 가능성, 답 일관성) 1~3점, judge 채점
- **비용**: 조건별 총 토큰, 호출 수, 소요 시간
- **수정 통계**: 문항당 평균 수정 횟수, 최종 실패 문항 수

### 기출 hold-out 실험
1. `exam_A`만으로 프로필 생성 → 시험 생성
2. `exam_B`와 비교:
   - 개념 커버리지: B의 각 문항과 가장 유사한 생성 문항의 임베딩 유사도 평균, 같은 주제 비율
   - 유형 분포 거리 (B의 실제 유형 비율 vs 생성 비율)
3. A↔B 바꿔서 반복

결과는 `outputs/<course>/experiments/<timestamp>/report.md`에 표로 저장 (+ CSV).

---

## 8. 구현 규칙

- **API 키**는 `.env`에서만 읽는다. 코드나 로그에 키를 남기지 않는다.
- **모든 LLM 호출은 `llm.py`를 거친다**: 캐시 확인 → 호출 → 재시도(지수 백오프, rate limit 대응) → JSON 파싱 → 토큰/시간 기록(`logs.jsonl`).
- 캐시 키 = hash(model, messages, temperature, 스키마 이름). `--no-cache` 옵션 제공. 실험 반복 생성 시에는 seed 인덱스를 키에 포함.
- 프롬프트는 `prompts/*.md` 파일로 분리. 코드 안에 긴 프롬프트 문자열 금지.
- 모든 출력 문항·해설은 **한국어**, 수식은 LaTeX.
- 각 스크립트는 `--course`, `--run-id` 인자를 받고, 중간 결과(JSON)를 저장해 어느 단계부터든 재실행 가능하게.
- 메모리 8GB: 임베딩은 배치 크기 작게(16), 임베딩 결과는 `.npy`로 저장해 재사용. 큰 모델을 로컬에 로드하지 않는다.
- 외부 프레임워크(LangChain, CrewAI, AutoGen) 사용하지 않는다. 순수 Python. (LangGraph 이전은 프로토타입 완성 후 선택 사항)
- 함수에 타입 힌트, 핵심 로직에 pytest (LLM 호출은 mock).

---

## 9. 구현 순서 (마일스톤)

각 단계 끝에 **완료 기준**을 확인하고 사용자에게 결과를 보여준 뒤 다음으로 진행한다.

### M0. 뼈대 (0.5일)
- 디렉토리, requirements, config.yaml, .env.example, `schemas.py`, `llm.py`(캐시·재시도·로그)
- ✅ 완료 기준: `python -m qgen.llm --ping`으로 config에 적힌 각 모델이 응답하고 캐시가 동작

### M1. 수집과 검색 (2일)
- `pdf_parser.py`: 페이지별 텍스트, 텍스트가 거의 없거나 수식·그림이 많은 페이지는 PNG로 렌더링 표시
- `chunker.py`: 슬라이드 1장 = 기본 1청크, 긴 페이지는 문단 단위 분할, 제목 보존
- `index.py` + `scripts/build_index.py`
- ✅ 완료 기준: 주제 키워드로 검색하면 관련 페이지가 top-5에 나오는지 5개 쿼리로 확인

### M2. 출제 프로필 (1.5일)
- Analyst 에이전트 + `scripts/make_profile.py`
- ✅ 완료 기준: profile.json이 스키마를 통과하고 evidence가 기출/메모를 실제로 가리킴. 사용자가 검토

### M3. 계획 + 생성 (2일)
- Planner, Generator, `render.py`
- ✅ 완료 기준: 검증 없이 시험 1세트가 exam.md로 렌더링됨. 유형 비율이 프로필과 일치

### M4. 검증 루프 (3일)
- `checks.py`, Solver, Reviewer, `pipeline.py` 루프
- ✅ 완료 기준: `scripts/generate_exam.py --course X` 한 번으로 검증된 시험 1세트 + 답안지 + 로그 생성. 루프에서 실제로 수정된 사례가 로그에 있음

### M5. 실험 (4일)
- `run_experiments.py`, `evaluate.py`, hold-out 실험, report.md
- ✅ 완료 기준: 4개 조건 × N세트 결과표 + hold-out 결과표 생성

### M6. (선택) UI
- Streamlit: 과목 선택 → 프로필 확인/수정 → 생성 → 시험지/답안 보기(LaTeX 렌더링) → 문항별 로그(수정 이력) 보기

---

## 10. 하지 말 것

- 기출 문항을 그대로 또는 숫자만 바꿔 출력하기
- Solver에게 정답 정보를 넘기기 (프롬프트, 필드, 캐시 어느 경로로도)
- 강의자료에 근거 없는 문항 통과시키기
- 수정 루프 무제한 반복
- 실험 조건마다 다른 ExamPlan 쓰기 (비교가 무의미해짐)
- 생성 모델과 같은 모델을 최종 평가자(judge)로 쓰기
