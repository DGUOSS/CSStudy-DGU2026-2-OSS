# question-ai — 문제 생성기

강의자료(PDF)와 기출·메모로 출제 경향에 맞는 문제를 만드는 멀티에이전트 프로토타입.
설계 명세는 [CLAUDE.md](CLAUDE.md).

## 처음 설치

`question-ai/` 폴더에서:

```bash
pip install -r requirements.txt   # torch는 CPU 버전. 마지막 줄의 -e . 로 qgen 패키지도 설치됨
cp .env.example .env              # .env에 API 키 3개(Gemini·OpenAI·Anthropic)를 넣는다. git에 올라가지 않음
```

- `-e .`(editable) 설치는 **설치한 폴더**를 가리킨다. 다른 폴더에 받은 적이 있으면 이 폴더에서 다시 설치한다.
  확인: `python -c "import qgen; print(qgen.__file__)"` 가 이 저장소 경로여야 한다.
- 임베딩 모델(`intfloat/multilingual-e5-small`, 약 470MB)은 처음 쓸 때 Hugging Face에서 자동으로 받는다.

## 과목 자료 넣기

```
data/<과목>/
├── lectures/     강의자료 (.pdf / .md / .txt)
├── past_exams/   기출 (있으면)
└── notes.md      시험 정보 메모 (있으면)
```

- 교안·기출 원본 PDF·이미지는 저작권 때문에 git에서 제외된다. **.md/.txt는 제외되지 않으니** 실제 기출을 옮겨 적은 파일은 커밋하지 않는다.
- `.md/.txt`는 `---` 줄 또는 `## 제목`을 슬라이드 경계로 본다.

## 검색 인덱스 만들기 (권장)

```bash
python scripts/build_index.py --course <과목>
python scripts/build_index.py --course <과목> --query "HTTP Status Codes"   # 만든 뒤 검색 결과 확인
```

- 결과: `data/<과목>/index/` (git 제외)
  - `chunks.json` 슬라이드 조각(글자·쪽·제목·그림 여부), `embeddings.npy` 임베딩, `meta.json`
  - `pages/*.png` 그림 위주·글자 부족 쪽 이미지 (아직 에이전트에게 전달하지 않음, 이슈 #3)
- 인덱스가 없거나 교안이 바뀌어 오래되면 **키워드 검색(BM25)으로 대신** 동작한다. 교안을 바꾸면 다시 만든다.
- 글자가 거의 없는 쪽(그림만 있거나 스캔본)은 경고를 출력한다. 스캔 PDF는 텍스트로 문제를 만들 수 없다.

## 문제 생성

```bash
python run.py --course <과목>               # 결과: outputs/<과목>/<실행시각>/
python run.py --course demo --no-cache      # 캐시 없이 (시간 측정할 때)
python run.py --course <과목> --new-profile # 출제 프로필 다시 만들기
```

- 결과 파일: `exam.md`(시험지), `answers.md`(정답·채점 기준·근거 쪽), `trace.json`(문항별 풀이·검토 기록),
  `logs.jsonl`(호출별 모델·토큰·시간: `api_sec` 응답, `wait_sec` 대기), `summary.json`(단계별·문항별 소요 시간)
- 에이전트별 모델은 `config.yaml`. 지금: 생성 = Gemini(무료), 풀이 검증 = OpenAI mini, 검토 = Claude haiku (유료 둘은 소액)
- 처음 실행 때 임베딩 모델을 불러오는 데 약 30초가 든다(대부분 torch 불러오기). 계속 켜져 있는 서버에서는 한 번만 든다.

## 검색이 동작하는 방식

1. Planner가 강의자료 **쪽 제목 목록**을 보고 문항을 계획한다. 주제(`topic`)는 한국어로, 검색용 제목(`source_titles`)은
   목록에서 **번역 없이 그대로** 1~3개 복사한다 (한 개념이면 1개, 비교 문항이면 개념마다 1개).
2. 그 제목들로 검색해 제목별 결과를 번갈아 합쳐 4쪽(`retrieval_top_k`)을 고른다.
   교안이 영어인데 한국어로 검색하면 관련 쪽을 잘 못 찾아서 원래 제목을 쓴다.
3. 고른 쪽의 **글자**를 Generator·Solver·Reviewer에게 근거로 넘긴다. 에이전트가 직접 검색하지는 않는다.

## 테스트

```bash
python -m pytest -q    # LLM·실제 임베딩 모델을 쓰지 않음 (가짜 인코더), 1초 안팎
```
