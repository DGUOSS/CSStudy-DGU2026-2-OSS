import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { AppShell } from '@/features/home/AppShell'
import { QUIZ_TOTAL } from './CourseChaptersPage'
import { QuizResult } from './QuizResult'
import { QuizSolve } from './QuizSolve'
import { type Entry, type Problem } from './quizTypes'

/** 퀴즈(/study/courses/:courseId/quiz?chapters=1,2): 문제를 받아 풀이 → 결과 화면으로 이어진다. */
export function StudyQuizPage() {
  return (
    <AppShell>
      <QuizLoader />
    </AppShell>
  )
}

function QuizLoader() {
  const courseId = Number(useParams().courseId)
  const [params] = useSearchParams()
  const qc = useQueryClient()
  const chapterIds = (params.get('chapters') ?? '')
    .split(',')
    .map(Number)
    .filter((n) => Number.isInteger(n) && n > 0)
  const chapterKey = chapterIds.join(',')

  // round: 새 문제로 다시 받을 때 올린다. retry: 틀린·건너뛴 문제만 다시 풀 때의 문제 목록
  const [round, setRound] = useState(0)
  const [retry, setRetry] = useState<Problem[] | null>(null)
  const [finished, setFinished] = useState<Entry[] | null>(null)

  const per = Math.ceil(QUIZ_TOTAL / Math.max(chapterIds.length, 1))
  const fetched = useQuery({
    queryKey: ['study-quiz', courseId, chapterKey, round],
    queryFn: async () => {
      const lists = await Promise.all(
        chapterIds.map((id) =>
          unwrap(
            api.GET('/api/v1/chapters/{chapter_id}/problems', {
              params: { path: { chapter_id: id }, query: { count: per } },
            }),
          ),
        ),
      )
      const seen = new Set<number>()
      return lists
        .flat()
        .filter((p) => !seen.has(p.id) && seen.add(p.id))
        .slice(0, QUIZ_TOTAL)
    },
    enabled: chapterIds.length > 0 && retry === null,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })

  const back = (
    <Link
      to={`/study/courses/${courseId}`}
      className="inline-flex items-center text-sm text-ink-2 hover:underline"
    >
      <ChevronLeft className="size-4" />
      단원 선택
    </Link>
  )

  if (chapterIds.length === 0)
    return (
      <>
        {back}
        <Empty>풀 단원이 선택되지 않았습니다. 단원 선택 화면에서 단원을 골라 주세요.</Empty>
      </>
    )

  const problems = retry ?? fetched.data
  if (!problems) {
    return fetched.error ? (
      <>
        {back}
        <ErrorText error={fetched.error} />
      </>
    ) : (
      <Loading />
    )
  }
  if (problems.length === 0)
    return (
      <>
        {back}
        <Empty>선택한 단원에는 아직 문제가 없습니다.</Empty>
      </>
    )

  // 풀이/결과를 새로 시작할 때마다 key가 바뀌어 상태가 초기화된다
  const sessionKey = `${chapterKey}-${round}-${retry ? retry.map((p) => p.id).join('.') : 'all'}`

  const restartFresh = () => {
    qc.invalidateQueries({ queryKey: ['courses', courseId] })
    setRetry(null)
    setFinished(null)
    setRound((r) => r + 1)
  }
  const retryProblems = (list: Problem[]) => {
    setRetry(list)
    setFinished(null)
  }

  return finished ? (
    <QuizResult
      key={sessionKey}
      courseId={courseId}
      problems={problems}
      entries={finished}
      onRetry={retryProblems}
      onRestart={restartFresh}
    />
  ) : (
    <QuizSolve key={sessionKey} problems={problems} onFinish={setFinished} />
  )
}

