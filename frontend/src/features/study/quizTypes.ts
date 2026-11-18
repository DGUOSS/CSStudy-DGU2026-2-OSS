import type { Schemas } from '@/api/client'

export type Problem = Schemas['ProblemOut']
export type Result = Schemas['AttemptResult']

/** 문제 하나의 풀이 상태. 채점은 '정답 확인'을 눌러야 서버에 기록된다(건너뛴 문제는 기록 안 됨). */
export type Entry = {
  /** 고른 보기(아직 제출 전일 수도 있음) */
  chosen: number | null
  result: Result | null
  skipped: boolean
}

export const emptyEntries = (problems: Problem[]): Entry[] =>
  problems.map(() => ({ chosen: null, result: null, skipped: false }))

export type Status = 'correct' | 'wrong' | 'skipped' | 'open'
export const statusOf = (e: Entry): Status =>
  e.result ? (e.result.correct ? 'correct' : 'wrong') : e.skipped ? 'skipped' : 'open'
