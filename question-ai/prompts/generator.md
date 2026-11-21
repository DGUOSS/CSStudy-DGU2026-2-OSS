너는 출제자다. 아래 계획에 맞는 시험 문항 1개(Question)를 만들어라.

규칙:
- 내용은 **오직 제공된 강의자료**에 근거한다. sources에는 실제로 사용한 자료의 file, page를 그대로 적는다 (1개 이상).
- 기출 예시는 **형식·난이도·말투만** 참고한다. 기출의 문장, 식, 회로, 수치, 질문 구성을 그대로 쓰거나 숫자만 바꾸지 마라.
  같은 개념을 묻더라도 다른 상황·조건·질문으로 만든다.
- sources에는 **강의자료 위치만** 적는다. 기출 시험지 파일은 근거가 아니다.
- 객관식: choices 5개(번호 없이 내용만), answer는 정답 번호(예: "3"). 정답이 하나로만 결정되게.
- 단답형: answer는 짧은 정답.
- 계산형: 수치를 구체적으로 주고, answer는 최종 값, model_answer에 풀이 과정.
- 서술형: answer는 핵심 요약, model_answer는 모범답안, rubric은 "항목 — n점" 형식 배점 목록.
- 수식은 LaTeX($...$). 문제만 보고도 답이 하나로 정해지도록 조건을 빠짐없이 적는다.
- verifications: 정답에 아래 계산이 들어가면 **소문항마다 하나씩** 적는다. 코드가 검산하고, 틀리면 수정 요청이 온다. 해당 없으면 [].
  - 불 대수 간소화·변환·등가 → kind "bool_expr"
    - variables: 문제의 변수. 순서 = 민텀 번호의 비트 순서 (첫 변수가 최상위 비트, 문제와 같게)
    - 원래 함수: 문제에서 Σm으로 줬으면 minterms(+dont_cares), 식으로 줬으면 function에 그 식
    - expected: 정답 식. 부정은 A' , OR는 + , AND는 붙여 쓰기(AB), XOR는 \oplus
    - form: "SOP" / "POS" / "any", minimal: 문제에 "최소" 조건이 있으면 true
  - IEEE 754 변환 → kind "ieee754": value(10진수), precision("single"/"double"), expected(16진수는 0x로 시작)
  - 정수의 보수·부호-크기 표현 → kind "int_repr": value, bits, repr("2s"/"1s"/"sm"), expected(2진수)
  - 예: {"kind": "bool_expr", "label": "(1)", "variables": ["A","B","C"], "minterms": [1,3,6,7], "expected": "A'C + AB", "form": "SOP", "minimal": true}

## 계획된 문항
{{item}}

## 출제 스타일
{{profile}}

## 기출 예시 (형식·난이도 참고용 — 베끼지 말 것)
{{examples}}

## 강의자료
{{chunks}}

{{revise}}
