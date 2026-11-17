import { useQueries } from '@tanstack/react-query'
import { api, unwrap } from '@/api/client'
import { useMyCourses } from '@/features/enrollments/queries'

export type SubjectSummary = {
  /** 과목 묶음 키(과목명). 내 강좌를 과목명으로 묶는다 */
  key: string
  name: string
  code: string | null
  courseCount: number
  /** 0~1. 아직 안 푼 개념은 0으로 센다(ChaptersTab과 같은 계산) */
  mastery: number
  attempts: number
  correct: number
}

/**
 * 홈 화면용 요약. 새 API 없이 기존 API만 조합한다.
 * 내 강좌(/me/courses, 수강 기록으로 들어갈 수 있는 강좌) → 강좌별 숙련도를 과목명으로 묶는다.
 * 쿼리 키가 mastery/queries.ts와 같아서 다른 화면에서 받은 캐시를 그대로 쓴다.
 */
export function useHomeSummary() {
  const mine = useMyCourses()
  const myCourses = mine.data?.courses ?? []

  const masteryQs = useQueries({
    queries: myCourses.map((c) => ({
      queryKey: ['courses', c.course_id, 'mastery'],
      queryFn: () =>
        unwrap(
          api.GET('/api/v1/courses/{course_id}/mastery', {
            params: { path: { course_id: c.course_id } },
          }),
        ),
    })),
  })

  const loading = mine.isPending || masteryQs.some((q) => q.isPending)
  const error = mine.error ?? masteryQs.find((q) => q.error)?.error ?? null

  const byName = new Map<string, SubjectSummary>()
  const conceptCount = new Map<string, number>()
  myCourses.forEach((c, j) => {
    const cur = byName.get(c.subject_name) ?? {
      key: c.subject_name,
      name: c.subject_name,
      code: c.sbj_no,
      courseCount: 0,
      mastery: 0,
      attempts: 0,
      correct: 0,
    }
    let concepts = 0
    let masterySum = 0
    for (const ch of masteryQs[j]?.data ?? []) {
      for (const k of ch.concepts) {
        concepts += 1
        cur.attempts += k.attempts
        cur.correct += k.correct
        if (k.attempts > 0) masterySum += k.mastery
      }
    }
    // 같은 과목의 강좌가 여럿이면 개념 수로 가중 평균한다
    const prevConcepts = conceptCount.get(c.subject_name) ?? 0
    const total = prevConcepts + concepts
    cur.mastery = total ? (cur.mastery * prevConcepts + masterySum) / total : 0
    conceptCount.set(c.subject_name, total)
    cur.courseCount += 1
    byName.set(c.subject_name, cur)
  })
  const summaries: SubjectSummary[] = [...byName.values()]

  // 개념 단위 기록의 합이라, 개념이 여러 개인 문제는 개념 수만큼 센다(근사치)
  const attempts = summaries.reduce((n, s) => n + s.attempts, 0)
  const correct = summaries.reduce((n, s) => n + s.correct, 0)

  return {
    loading,
    error,
    subjects: summaries,
    totals: {
      attempts,
      correct,
      wrong: attempts - correct,
      accuracy: attempts ? correct / attempts : null,
    },
  }
}

export type DeadlineItem = {
  id: number | string
  title: string
  courseName: string
  /** ISO 날짜시간 */
  due: string
}

/**
 * 시험·과제 일정. 백엔드에 아직 API가 없어서 빈 목록을 돌려준다.
 * 일정 API(예: GET /api/v1/me/deadlines)가 생기면 여기만 바꾸면 홈의
 * '이번 주 시험 과제'·'다가오는 일정'·캘린더 점이 함께 채워진다.
 */
export function useDeadlines(): { data: DeadlineItem[] } {
  return { data: [] }
}
