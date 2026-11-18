# 디자인 명세서

새 디자인 화면(`/home`, `/study/*`)을 프론트에서 구현·수정할 때 참고하는 문서다.
값은 모두 현재 코드(`frontend/src/index.css`, `frontend/src/features/home`, `frontend/src/features/study`)에서 확인한 것이다. 코드를 바꾸면 이 문서도 같이 고친다.

- 기능 명세는 `docs/SPEC.md`, DB는 `docs/DB.md`를 본다.

## 1. 적용 범위와 켜는 법

새 디자인은 기존 화면과 나란히 존재한다. 기존 화면은 건드리지 않았다.

| 구분 | 틀(Layout) | 경로 |
| --- | --- | --- |
| 새 디자인 | `features/home/AppShell` (사이드바 + 본문) | `/home`, `/study`, `/study/find`, `/study/import`, `/study/courses/:courseId`, `/study/courses/:courseId/quiz` |
| 기존 화면 | `components/Layout` | `/`, `/find`, `/ndrims`, `/subjects/:id`, `/courses/:id` 등 |

- 첫 화면(`/`)은 `frontend/.env.local`에 `VITE_DESIGN=on`이 있을 때만 `/home`으로 이동한다. 없으면 기존 `HomePage`가 뜬다.
- 새 화면 경로는 `src/App.tsx`에 한 줄 등록한다.

## 2. 색

색은 두 묶음이다. shadcn 토큰은 기존 화면이 쓰므로 바꾸지 않고, 새 디자인 색은 `@theme`에 **추가만** 했다. 색을 바꿀 때는 `src/index.css`에서만 고친다.

### 새 디자인 색 (`@theme`)

Tailwind 클래스는 `bg-navy`, `text-ink-2`, `border-home-line`처럼 쓴다.

| 토큰 | 값 | 용도 |
| --- | --- | --- |
| `navy` | `#1f3a6e` | 주 색. 기본 버튼, 활성 메뉴 글자, 진행 막대 |
| `navy-deep` | `#172c57` | 히어로 배경, 기본 버튼 hover |
| `navy-tint` | `#e6ebf5` | 활성 메뉴 배경, 연한 버튼 hover, 강좌 행 배경 |
| `gold` | `#e3b55b` | 보조 진행 막대(챕터 안쪽 막대) |
| `gold-soft` | `#f6e7c5` | 금색 계열 연한 배경 |
| `home-bg` | `#f4f5f8` | 화면 바탕, 입력창 비활성 배경, 카드 안쪽 영역 |
| `home-line` | `#e1e5ee` | 카드·사이드바·입력창 테두리 |
| `ink-2` | `#566075` | 보조 글자(설명, 메타 정보) |
| `tone-blue` | `#dde5f5` | 히어로 과목 카드 1번, 태그 배경 |
| `tone-gold` | `#f3e7cc` | 히어로 과목 카드 2번 |
| `tone-gray` | `#d9dee8` | 히어로 과목 카드 3번 |

### 상태 색 (퀴즈)

토큰 없이 코드에 직접 쓰인 값이다. 같은 의미에는 같은 값을 쓴다.

| 의미 | 값 |
| --- | --- |
| 정답 | `#2e8b6a` |
| 오답 | `#c8453f` |
| 진행 막대 바탕 | `#e6eaf2` |

### 기존 shadcn 토큰 (참고)

`--primary`(동국 주황빛 빨강, `oklch(0.55 0.2 25)`), `--background`, `--border` 등은 기존 화면용이다. 새 화면에서 shadcn 컴포넌트를 쓸 때 주 색이 빨강으로 나오므로, 필요하면 `ImportPage`처럼 감싸는 요소에 `[--primary:var(--color-navy)] [--ring:var(--color-navy)]`를 준다.

## 3. 글꼴·글자 크기

- 글꼴: `Pretendard` → `system-ui` → `Segoe UI` → `Malgun Gothic` → `sans-serif` (`--font-sans`)
- 글자 크기는 Tailwind 클래스를 그대로 쓴다.

| 용도 | 클래스 |
| --- | --- |
| 화면 제목 (h1) | `text-2xl font-bold` |
| 히어로 문구 | `text-xl font-medium` (흰색) |
| 섹션 제목 (h2) | `text-xl font-bold` 또는 카드 안은 `text-lg font-bold` |
| 본문·버튼 | `text-[15px]` (버튼은 `font-bold`) |
| 보조 설명 | `text-sm text-ink-2` |
| 메타·라벨 | `text-xs` 또는 `text-[13px]`, 라벨은 `font-bold text-ink-2` |

## 4. 모양

- 기본 반경 변수 `--radius`는 `0.625rem`이다. 새 화면은 반경을 클래스로 직접 지정한다.
- 버튼·태그·진행 막대: `rounded-full`
- 카드: `rounded-2xl`, 큰 영역(히어로): `rounded-3xl`, 안쪽 박스·입력창·메뉴 항목: `rounded-xl`
- 그림자는 쓰지 않는다. 카드는 `border border-home-line bg-white`로 구분한다.
- 아이콘은 `lucide-react`. 사이드바는 크기 20·선 굵기 1.8, 버튼 안은 16을 쓴다.

## 5. 공통 컴포넌트

### 화면 틀 `AppShell` (`features/home/AppShell.tsx`)

- 새 디자인 화면은 모두 `<AppShell>`로 감싼다. 로그인 확인도 여기서 한다. 로그인 전이면 `/login`으로 보내고, 로그인 후에만 `children`을 그린다. 안쪽 화면은 API를 안전하게 호출해도 된다.
- 바탕 `bg-home-bg`, 본문은 `max-w-[960px]`로 가운데 정렬, 항목 사이 간격 `gap-7`.
- 본문 여백: `px-6 pt-8 pb-12`, 큰 화면(`lg`)에서 `px-10`.

### 사이드바 `HomeSidebar`

- 너비 `w-60`. **`md` 미만에서는 숨겨진다(`hidden md:flex`).** 모바일 메뉴는 아직 없다.
- 메뉴: 홈(`/home`), 학습(`/study`). 생활·학교는 준비 중이라 눌리지 않고 흐리게(`text-ink-2/50`) 표시된다.
- 메뉴 항목: 높이 `h-12`, `rounded-xl`, `px-4`. 활성은 `bg-navy-tint font-bold text-navy`, 비활성은 `text-ink-2`, hover `bg-home-bg`.
- 하단: 관리자만 `관리` 링크, `내 요청`, 사용자 이름, 로그아웃 버튼.

### 버튼

| 종류 | 클래스 요약 | 예 |
| --- | --- | --- |
| 기본 | `h-11 rounded-full bg-navy px-5~6 text-[15px] font-bold text-white hover:bg-navy-deep` | 강좌 찾기, 검색, 퀴즈 시작 |
| 보조 | `h-11 rounded-full border border-home-line bg-white px-5 font-bold text-navy hover:bg-navy-tint` | 수강 기록 가져오기 |
| 히어로 안 | `h-11 rounded-full bg-white px-5 font-bold text-navy hover:bg-navy-tint` | 학습하러 가기 |
| 비활성 | `disabled:opacity-40 disabled:cursor-not-allowed` | |

### 입력창·라벨 (`FindPage`)

- 입력창: `h-11 rounded-xl border border-home-line bg-white px-3 text-[15px]`, 포커스 `ring-2 ring-navy/40`, 비활성 `bg-home-bg`.
- 라벨은 입력창 위에 `text-xs font-bold text-ink-2`로 둔다 (`Field` 컴포넌트).

### 카드

- 기본: `rounded-2xl border border-home-line bg-white p-5`
- 안쪽 강조 행(강좌 선택): `rounded-xl bg-navy-tint px-4 py-3 hover:bg-tone-blue`

### 상태 표시 (`components/States`)

`Loading`, `Empty`, `ErrorText`를 공통으로 쓴다. 데이터를 불러오는 화면은 이 셋을 빠뜨리지 않는다.

### 진행 막대

높이 `h-1.5`~`h-2`, `rounded-full`. 바탕은 `bg-[#e6eaf2]` 또는 흰색 반투명, 채움은 주 막대 `bg-navy`, 보조 막대 `bg-gold`.

## 6. 화면별 구성

### 홈 `/home` (`features/home/HomePage`)

위에서 아래로, 큰 화면(`lg`)에서는 본문과 오른쪽 열(`360px`)로 나뉜다.

1. **Hero** (`bg-navy-deep`, `rounded-3xl`, `p-8`): 왼쪽에 인사 문구 + 「학습하러 가기」 버튼, 오른쪽에 내 과목 카드 최대 3개. 카드 바탕은 `tone-blue → tone-gold → tone-gray` 순서로 돈다. 카드 안: 아이콘, 과목명, `강좌 N개 | 숙련도 N%`, 진행 막대.
2. 왼쪽 열
   - **Stats** 「학습 현황」: 카드 3개(3열). 숫자는 `text-4xl font-bold`, 아래에 `text-sm text-ink-2` 라벨. 항목은 `푼 문제 (누적)`, `정답률`(없으면 `-`), `틀린 횟수 (누적)`.
   - **WeekDeadlines** 「이번 주 시험 과제」: 오늘부터 7일 안의 일정 목록. 한 줄 구성은 아이콘 상자(`size-11`, `tone-blue`) + 제목·과목명 + `M월 D일` + D-day 태그(`gold-soft`). D-day 표기는 `D-Day`, `D-3`, 지난 일정은 `D+2`. 없으면 `Empty` 문구.
3. 오른쪽 열 (`lg`에서 360px)
   - **Calendar**: `rounded-[20px]` 카드, 월 이동 버튼(`이전 달`/`다음 달`), 일요일 시작 7열. 오늘은 `bg-navy` 흰 글자, 이번 달이 아닌 날은 흐리게(`text-ink-2/50`), 일정이 있는 날은 숫자 아래에 `bg-gold` 점(5px).
   - **Upcoming** 「다가오는 일정」: 오늘 이후 일정 중 가까운 순 3개. 아이콘 상자(`size-12`, `bg-navy` + 금색 아이콘), 위에 `M월 D일 · HH:MM`, 아래에 제목. 없으면 `Empty` 문구.
- 섹션 제목은 `SectionHeader`(`text-xl font-bold`)를 쓴다.
- 목록 카드는 `overflow-hidden rounded-2xl border border-home-line bg-white`, 행 사이 구분선 `border-b border-home-line`(마지막 행 제외).

- 과목이 없으면 히어로에 안내 문구를, 불러오는 중에는 `과목 불러오는 중…`을 보인다.
- 데이터는 모두 기존 API(내 과목·강좌·숙련도)에서 온다 (`home/queries.ts`).

### 학습 `/study` (`study/StudyPage`)

- 제목 「학습」 + 설명, 오른쪽에 보조 버튼 「수강 기록 가져오기」와 기본 버튼 「강좌 찾기」.
- 내 강좌를 **과목명으로 묶어** 2열 카드로 보인다. 카드 안에 교수별 행(`navy-tint`)이 있고, 수강 중/수강함과 학기를 표시한다.
- 내 강좌가 없으면 `Empty`로 안내. 아래에 「공용 강좌」 섹션이 있을 수 있다.

### 강좌 찾기 `/study/find` (`study/FindPage`)

- 검색 폼 카드(3열 그리드): 학기, 대학, 학과, 이수구분, 과목명·학수번호, 교수명 + 검색 버튼.
- 결과는 카드 목록. 강좌가 열려 있지 않으면 「열어 달라고 요청」 버튼(요청 인원 표시)을 보인다.

### 수강 기록 가져오기 `/study/import` (`study/ImportPage`)

- 「← 학습으로」 링크, 제목·설명, 흰 카드 안에 `ImportPanel`을 넣는다. 엔드림스 비밀번호는 서비스로 오지 않는다는 안내 문구를 유지한다.

### 챕터 `/study/courses/:courseId` (`study/CourseChaptersPage`)

- 챕터(단원) 카드 목록. 카드마다 숙련도 막대(`navy`)와 펼친 영역(`bg-home-bg`)의 세부 막대(`gold`)가 있다. 단원을 골라서 퀴즈를 푼다.
- 접이식 「참고할 족보 고르기」(`details`).
- 화면 아래에 **고정 바**(`fixed bottom-0`, `bg-white/95 backdrop-blur`, 큰 화면에서 `md:left-60`로 사이드바 폭만큼 띄움)가 있다. 왼쪽에 `N개 단원 선택 · 문제 최대 8개`(고르지 않았으면 `단원을 선택해 주세요`), 오른쪽에 「퀴즈 시작」 기본 버튼(단원을 고르기 전에는 비활성). 문제 수 8은 `QUIZ_TOTAL` 상수다.
- 고정 바가 본문을 가리지 않도록 본문 아래쪽에 여백이 필요하다.

### 퀴즈 풀이 `/study/courses/:courseId/quiz` (`study/QuizSolve`)

- 위쪽: 제목 「퀴즈 풀이」와 `현재 / 전체` 번호, 오른쪽에 「결과 보기」 윤곽선 버튼(`border-navy`). 모든 문제를 풀거나 건너뛰기 전에는 비활성이고, 마우스를 올리면 `모든 문제를 풀거나 건너뛰면 결과를 볼 수 있어요`가 보인다.
- 문제 번호 `nav`(`aria-label="문제 번호"`): 문제마다 상태가 있다. `correct`(정답) / `wrong`(오답) / `skipped`(건너뜀) / `open`(안 푼 문제). 번호로 아무 문제나 오갈 수 있다.
- 보기 버튼: 선택한 보기는 `border-navy bg-navy-tint`, 정답은 초록 테두리·배경(`#2e8b6a` / `#e8f4ef`)과 체크 아이콘, 고른 오답은 빨강 테두리·배경(`#c8453f` / `#fbeceb`)과 X 아이콘. 보기 번호는 `size-6` 원형 배지, 보기 글자는 `font-mono`.
- 아래 버튼 줄: 왼쪽에 「이전」(첫 문제에서는 비활성), 오른쪽은 채점 전에는 「건너뛰기」(`bg-gold-soft`)와 「정답 확인」(기본 버튼), 채점 후에는 「다음 문제」. 마지막 문제에서 모두 끝났으면 「다음 문제」 대신 「결과 보기」가 뜬다.
- 「정답 확인」은 보기를 고르기 전에는 비활성이고, 채점 중에는 `채점 중…`으로 바뀐다. 채점 후에는 해설이 보기 아래에 나온다.
- 채점은 「정답 확인」을 눌러야 서버에 기록된다. 건너뛴 문제는 기록되지 않는다.

### 퀴즈 결과 (`study/QuizResult`)

- 요약 수치: 정답률(강조 `navy`), 정답(`#2e8b6a`), 오답(`#c8453f`).
- 「취약점 정리」: 틀리거나 건너뛴 문제의 개념을 숙련도가 낮은 순으로 3개.
- 틀린·건너뛴 문제 복습 → 맞힌 문제 목록(`정답 ✓`).
- 건너뛴 문제에는 정답·해설을 보여 주지 않는다. 다시 풀면 볼 수 있다는 문구를 쓴다.

## 7. 구현할 때 지킬 것

- 새 화면은 `AppShell`로 감싸고 `App.tsx`의 `Layout` **밖**에 경로를 등록한다.
- 색은 위 토큰 클래스를 쓴다. 새 색이 필요하면 `index.css`의 `@theme`에 추가하고 이 문서 2절도 고친다. 코드에 `#xxxxxx`를 직접 쓰는 것은 상태 색처럼 이미 정한 경우만 한다.
- 백엔드 호출은 `src/api/client.ts`의 `api` + `unwrap`만 쓴다.
- 작업을 마치기 전에 `pnpm typecheck && pnpm lint && pnpm build`를 돌린다.

## 8. 아직 없는 것

- 모바일 사이드바(`md` 미만에서 숨기기만 함), 다크 모드(새 디자인 색은 라이트 값만 있음)
- 생활·학교 메뉴(준비 중)
- 화면 캡처


## 관심 학과 공지

새 홈의 일정 영역 아래에 전체 너비 `NoticesPanel`을 배치한다. 기존 홈에서도 같은 컴포넌트를 사용한다. 네이비 버튼과 학과 태그, 골드 중요 표시, `rounded-2xl` 흰 카드를 사용한다. 학과 탭은 한 줄 가로 스크롤이다. 기본 목록은 5개이며 더 보기를 제공한다.

학과 설정은 네이티브 dialog로 열고 최대 8개 선택, 검색, 선택한 학과 해제 칩을 제공한다. 검색/선택 칩과 하단 저장 영역은 유지하고 학과 목록만 스크롤한다. 모바일에서는 한 열로 배치한다. 공지 제목을 누르면 별도 dialog에서 본문과 원문 링크를 확인한다. Escape/닫기를 지원하고 저장 중에는 닫기를 막는다.

학과 선택 행은 체크박스 없이 별 아이콘을 둔 토글 버튼이다. 별 또는 학과명을 누르면 선택/해제되며 선택 시 금색으로 채워진 별과 네이비 틴트 배경을 표시한다. `aria-pressed`로 선택 상태를 제공하고 Enter/Space로 조작할 수 있다.
