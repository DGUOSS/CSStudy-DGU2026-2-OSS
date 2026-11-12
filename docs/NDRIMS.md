# 엔드림스(nDRIMS) 데이터 구조 (2026-11-12 조사)

학생이 직접 로그인한 브라우저에서 화면이 주고받는 요청을 기록해 확인했다. 비밀번호와 쿠키는 기록하지 않았고, 개인 값은 가린 채 칸 이름만 봤다.

## 공통
- 화면은 eXbuilder6로 만들어져 있다. 데이터는 `POST https://ndrims.dongguk.edu/<경로>.do` (form 인코딩)로 요청하고 JSON으로 받는다.
- 요청 값 이름은 `@d1#칸이름` 형식이다. 화면 실행 정보(`_runningNana`, `_runningMainOpenKey`, `_runningLoginIdenNo`)가 함께 붙는다.
- 응답은 `{"dsMain": [ {행}, ... ]}`처럼 데이터셋 이름에 행 목록이 들어 있다.
- 학기 코드: `CM160.10` 1학기, `CM160.11` 여름학기, `CM160.20` 2학기, `CM160.21` 겨울학기, `CM160.99` 공통학기
- 학부 기관 코드 예: `OPEN_ORGN_CLSF_CD = CM015.110`

## 화면별 데이터
| 메뉴 | 요청 경로 | 보내는 값 | 받는 행의 주요 칸 |
|---|---|---|---|
| 수강신청 > 수강신청내역확인 | `/ed/edc/regi/EdcRegi170/doList.do` | `OPEN_YY`, `OPEN_SEM_CD`, `STD_NO` | `OPEN_YY`, `OPEN_SEM_CD`, `SBJ_NO`(학수번호), `SBJ_NM`, `DVCLS`(분반), `TMTBL_KOR_DSC`(시간), `CPDIV_NM`(이수구분). **교수 칸 없음** |
| 성적 > 전체성적조회 | `/ed/edd/rec/EddRec050/doList.do` | `STD_NO` | `YY`, `SEM_CD`, `SEM_NM`, `SBJ_NO`, `SBJ_NM`, `DVCLS`, `EMP_NM`(교수명), `CDT`(학점), 성적 칸들 |
| 수업/강의평가 > 종합강의시간표조회 | `/ed/edc/lesn/EdcLesn010/doList.do` | `OPEN_YY`, `OPEN_SEM_CD`, 학과 등 필터 | `OPEN_YY`, `OPEN_SEM_CD`, `SBJ_NO`, `SBJ_NM`, `DVCLS`, **`EMP_NO`(교원번호)**, `EMP_NM`, `MAIN_PROF_YN`, `CDT`, `DPT_NM`, `TMTBL_KOR_DSC`, `ROOM_KOR_DSC`, 평가 비율(`MID_/FNL_/ATND_/PROJ_EVAL_RATE`), `PLAN_URL`(강의계획서) |
| 학생 기본 정보 | `/ed/sys/EdbStdInfo/doList.do` | `STD_NO` | 학번, 이름, 학과, 연락처 등. **가져오지 않는다** |
| 메뉴 목록 | `/unis/main/view/menu/doListUserMenuListTop.do` | - | `MENU_NM`, `FULL_PATH_NM` (207개) |

## 우리 DB와 맞추는 방법
- **개설 강좌 하나 = (연도, 학기 코드, 학수번호, 분반)**. 네 값이 같으면 같은 수업이다.
- 학수번호는 학기와 교수가 달라도 같다. 그래서 학수번호는 **과목**, 교원번호(`EMP_NO`)는 **교수**를 가리킨다. 강좌는 과목 + 교수다.
- 학생 수강 기록(수강신청내역·성적)에는 교원번호가 없다. 그래서 위 네 값으로 종합강의시간표의 행을 찾아 교수(교원번호)를 확정한다. 이름이 같은 교수도 구분된다.
- 종합강의시간표는 과목·교수·강좌 자동 생성에도 쓴다. 평가 비율과 강의계획서 링크는 강좌 정보로 쓸 수 있다.

## 가져오지 않는 것
- 성적, 학점, 평점, 석차, 학생 기본 정보(연락처, 주소 등). 학생 기록에서는 과목을 찾는 데 필요한 칸(연도, 학기, 학수번호, 분반, 과목명, 교수명)만 쓴다.

## 사이트에서의 흐름 (구현)
- 학생: 첫 화면 → 즐겨찾기 버튼 끌어다 놓기 → 엔드림스 열기 → 직접 로그인 → 아무 화면에서 즐겨찾기 누르기 → 끝
  - 버튼 코드: `frontend/src/features/ndrims/bookmarklet.ts`. 로그인한 창 안에서 엔드림스 화면과 같은 순서로 직접 요청한다: `doUserLoginAccs`(NANA) → `doListUserMenuListTop`(dmUserInfo: LOGIN_IDEN_NO, MAIN_OPEN_KEY, 학번) → `doListUserMenuListLeft`(화면별 NANA, PGM_URL로 찾음) → `EddRec050`(지난 학기), `EdcRegi170`(이번 학기). 성적 칸은 버린다. 2026-11-12 실제 엔드림스에서 이 순서로 받아지는 것을 확인했다.
  - 상자에 단계별 진단(칸 이름·건수만)을 보인다. 바로 못 받으면 화면을 열어 모으는 방식으로 넘어간다.
  - 보내기: 우리 사이트가 연 창이면 `postMessage` 후 받았다는 답(ack)을 기다린다. 답이 없거나 창 연결이 끊겼으면 우리 사이트 `/ndrims#<기록>`을 새 탭으로 연다(# 뒤는 서버로 가지 않음) → `POST /me/ndrims/import`
- 관리자: 종합강의시간표조회를 같은 방법으로 보내면 `POST /admin/catalog/import`로 개설 목록이 저장된다.
- 강좌는 요청 + 교안이 있어야 열린다(관리자 승인). 열리면 기다리던 수강 기록이 자동으로 이어진다.
- 출입: 수강 기록의 학수번호 + 교수(교원번호, 없으면 이름)로 판단. 학기와 상관없다. 같은 과목의 다른 교수 강좌는 잠긴다.
- 고려하지 않는 것: 공동 강의(대표 교수만), 기록 조작(브라우저에서 오므로 막을 수 없음. 개설 목록과 대조하는 정도)
