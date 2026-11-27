// 선지 글자 모양: 코드 선지(예: `int (*fp)(int, int);`, `char c = 'a';`)만 고정폭 글꼴로,
// 한글 문장 선지는 본문 글꼴로 보여 준다. 고정폭 글꼴에는 한글이 없어 다른 글꼴로 대신 그려져 어색하기 때문
const CODE_MARK = /[;{}()=*#"'<>[\]]|->|\+\+|--/

export function looksLikeCode(text: string): boolean {
  return CODE_MARK.test(text)
}

/** 선지 글자에 붙일 class. 코드는 줄 끝에서 아무 데서나 줄바꿈, 한글 문장은 단어 단위로 줄바꿈 */
export function choiceTextClass(text: string): string {
  // 글자 크기와 줄 높이(24px = 번호 동그라미 높이)를 한 class로 쓴다. 따로 쓰면(leading-6 + text-sm)
  // cn(tailwind-merge)이 text-sm을 줄 높이까지 정하는 것으로 보고 leading-6을 지워 버린다
  return looksLikeCode(text) ? 'font-mono text-sm/6 break-all' : 'text-[15px]/6 break-keep'
}
