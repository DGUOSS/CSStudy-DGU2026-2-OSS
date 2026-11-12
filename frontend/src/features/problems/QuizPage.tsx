import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronLeft, RotateCcw, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { api, ApiError, type Schemas, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { pct } from '@/features/mastery/queries'
import { cn } from '@/lib/utils'

const COUNT = 5
type Result = Schemas['AttemptResult']
type ProbeResult = Schemas['MisconceptionProbeAnswerResult']

export function QuizPage() {
  const courseId = Number(useParams().courseId)
  const chapterId = Number(useParams().chapterId)
  const [searchParams] = useSearchParams()
  const focusProblemId = Number(searchParams.get('problemId') ?? 0)
  const qc = useQueryClient()
  const [round, setRound] = useState(0)

  const problems = useQuery({
    queryKey: ['quiz', chapterId, round, focusProblemId],
    queryFn: async () => {
      if (focusProblemId) {
        const problem = await unwrap(api.GET('/api/v1/problems/{problem_id}', {
          params: { path: { problem_id: focusProblemId } },
        }))
        return [problem]
      }
      return unwrap(
        api.GET('/api/v1/chapters/{chapter_id}/problems', {
          params: { path: { chapter_id: chapterId }, query: { count: COUNT } },
        }),
      )
    },
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })
  const [index, setIndex] = useState(0)
  const [results, setResults] = useState<Result[]>([])

  const back = (
    <Link
      to={`/courses/${courseId}`}
      className="inline-flex items-center text-sm text-muted-foreground"
    >
      <ChevronLeft className="size-4" />
      챕터 목록
    </Link>
  )

  if (problems.isPending) return <Loading />
  if (!problems.data) return <ErrorText error={problems.error} />
  if (problems.data.length === 0) return <Empty>이 챕터에는 아직 문제가 없습니다.</Empty>

  const list = problems.data
  const done = index >= list.length

  const restart = () => {
    qc.invalidateQueries({ queryKey: ['courses', courseId] })
    setRound((r) => r + 1)
    setIndex(0)
    setResults([])
  }

  if (done) {
    const correct = results.filter((r) => r.correct).length
    return (
      <div className="flex flex-col gap-5">
        {back}
        <Card>
          <CardHeader>
            <div className="text-lg font-semibold">
              {list.length}문제 중 {correct}문제 맞혔습니다
            </div>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button onClick={restart}>
              <RotateCcw />
              {focusProblemId ? '같은 문제 다시 풀기' : '이어서 더 풀기'}
            </Button>
            <Link
              to={`/courses/${courseId}?tab=mastery`}
              className={buttonVariants({ variant: 'outline' })}
            >
              숙련도 보기
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {back}
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <span>
          {index + 1} / {list.length}
        </span>
        <Progress value={(index / list.length) * 100} className="max-w-48" />
      </div>
      <ProblemCard
        key={list[index].id}
        problem={list[index]}
        onAnswered={(r) => setResults((prev) => [...prev, r])}
        onNext={() => setIndex((i) => i + 1)}
        isLast={index === list.length - 1}
      />
    </div>
  )
}

function ProblemCard({
  problem,
  onAnswered,
  onNext,
  isLast,
}: {
  problem: Schemas['ProblemOut']
  onAnswered: (r: Result) => void
  onNext: () => void
  isLast: boolean
}) {
  const [chosen, setChosen] = useState<number | null>(null)
  const [probeChosen, setProbeChosen] = useState<number | null>(null)
  const qc = useQueryClient()
  const submit = useMutation({
    mutationFn: (chosen_index: number) =>
      unwrap(
        api.POST('/api/v1/problems/{problem_id}/attempts', {
          params: { path: { problem_id: problem.id } },
          body: { chosen_index },
        }),
      ),
    onSuccess: onAnswered,
  })
  const result = submit.data
  const probeSubmit = useMutation({
    mutationFn: (chosen_index: number) =>
      unwrap(
        api.POST('/api/v1/attempts/{attempt_id}/misconception-probe', {
          params: { path: { attempt_id: result!.attempt_id } },
          body: { chosen_index },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['misconception-results'] }),
  })
  const probeResult = probeSubmit.data
  const probeUnavailable = probeSubmit.error instanceof ApiError && probeSubmit.error.status === 404
  const waitingForProbe = !!result?.misconception_probe && !probeResult && !probeUnavailable
  const reveal = !!result && !waitingForProbe

  const choose = (i: number) => {
    if (result || submit.isPending) return
    setChosen(i)
    submit.mutate(i)
  }

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap gap-1">
          {problem.concepts.map((c) => (
            <Badge key={c.id} variant="secondary">
              {c.name}
            </Badge>
          ))}
          {problem.origin === 'sample' && <Badge variant="outline">샘플 문제</Badge>}
        </div>
        <p className="whitespace-pre-wrap text-base font-medium leading-relaxed">
          {problem.question}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {problem.choices.map((choice, i) => {
          const isAnswer = reveal && i === result?.answer_index
          const isWrongPick = reveal && i === chosen && !result?.correct
          return (
            <button
              key={choice}
              type="button"
              onClick={() => choose(i)}
              disabled={!!result || submit.isPending}
              className={cn(
                'flex items-start gap-3 rounded-lg border px-4 py-3 text-left text-sm transition-colors',
                !result && 'cursor-pointer hover:bg-accent',
                chosen === i && !result && 'border-primary',
                isAnswer && 'border-success bg-success/10',
                isWrongPick && 'border-destructive bg-destructive/10',
              )}
            >
              <span className="font-semibold text-muted-foreground">{i + 1}</span>
              <span className="flex-1 whitespace-pre-wrap font-mono">{choice}</span>
              {isAnswer && <Check className="size-4 text-success" />}
              {isWrongPick && <X className="size-4 text-destructive" />}
            </button>
          )
        })}
        <ErrorText error={submit.error} />
        {result?.misconception_probe && !probeUnavailable && (
          <div className="mt-3 flex flex-col gap-3 rounded-lg border border-primary/40 p-4 text-sm">
            <p className="font-semibold">한 가지를 더 확인해 볼게요</p>
            <p className="text-muted-foreground">처음 답의 정답과 해설은 확인 문제를 푼 뒤에 보여드립니다. 이 답은 숙련도 점수에 반영되지 않습니다.</p>
            <p className="whitespace-pre-wrap font-medium">{result.misconception_probe.question}</p>
            <div className="flex flex-col gap-2">
              {result.misconception_probe.choices.map((choice, i) => (
                <button
                  key={`${i}-${choice}`}
                  type="button"
                  disabled={!!probeResult || probeSubmit.isPending}
                  onClick={() => { setProbeChosen(i); probeSubmit.mutate(i) }}
                  className={cn(
                    'flex cursor-pointer gap-3 rounded-lg border px-4 py-3 text-left disabled:cursor-default',
                    probeChosen === i && !probeResult && 'border-primary bg-primary/10',
                    probeResult && i === probeResult.answer_index && 'border-success bg-success/10',
                    probeResult && i === probeChosen && !probeResult.correct && 'border-destructive bg-destructive/10',
                  )}
                >
                  <span className="font-semibold text-muted-foreground">{i + 1}</span>
                  <span className="whitespace-pre-wrap">{choice}</span>
                </button>
              ))}
            </div>
            <ErrorText error={probeSubmit.error} />
            {probeResult && <ProbeExplanation result={probeResult} />}
          </div>
        )}
        {probeUnavailable && <p className="mt-2 text-sm text-muted-foreground">확인 문제가 검토 중으로 변경되어 원래 문제의 해설을 보여드립니다.</p>}
        {reveal && <Explanation result={result} />}
        {reveal && (
          <Button className="mt-2 self-end" onClick={onNext}>
            {isLast ? '결과 보기' : '다음 문제'}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

function ProbeExplanation({ result }: { result: ProbeResult }) {
  const [showPage, setShowPage] = useState(false)
  const page = useQuery({
    queryKey: ['material-page', result.source.material_id, result.source.page],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/materials/{material_id}/pages/{page}', {
          params: { path: { material_id: result.source.material_id, page: result.source.page! } },
        }),
      ),
    enabled: showPage && !!result.source.page,
  })
  return (
    <div className="grid gap-3 rounded-md bg-muted p-4">
      <p className="font-semibold">{result.title}</p>
      <p>{result.detail}</p>
      <p><span className="font-medium">추정한 생각:</span> {result.hypothesis}</p>
      <p><span className="font-medium">확인 문제 해설:</span> {result.explanation}</p>
      <blockquote className="border-l-2 border-primary pl-3 text-muted-foreground">
        {result.evidence}
        <div className="mt-1 text-xs">— {result.source.title} {result.source.page}쪽{' '}
          {result.source.page && <button type="button" className="cursor-pointer text-primary underline" onClick={() => setShowPage((value) => !value)}>{showPage ? '접기' : '교안 보기'}</button>}
        </div>
      </blockquote>
      {showPage && <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md border bg-card p-3 text-xs">{page.data?.text ?? '불러오는 중…'}</pre>}
    </div>
  )
}

function Explanation({ result }: { result: Result }) {
  const [showPage, setShowPage] = useState(false)
  const source = result.source
  const page = useQuery({
    queryKey: ['material-page', source?.material_id, source?.page],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/materials/{material_id}/pages/{page}', {
          params: { path: { material_id: source!.material_id, page: source!.page! } },
        }),
      ),
    enabled: showPage && !!source?.page,
  })

  return (
    <div className="mt-2 flex flex-col gap-3 rounded-lg bg-muted p-4 text-sm">
      <div className={cn('font-semibold', result.correct ? 'text-success' : 'text-destructive')}>
        {result.correct ? '정답입니다' : `오답입니다 · 정답 ${result.answer_index + 1}번`}
      </div>
      <p className="whitespace-pre-wrap leading-relaxed">{result.explanation}</p>
      {result.evidence && (
        <blockquote className="border-l-2 border-primary pl-3 text-muted-foreground">
          {result.evidence}
          {source && (
            <div className="mt-1 text-xs">
              — {source.title}
              {source.page && (
                <>
                  {' '}
                  {source.page}쪽{' '}
                  <button
                    type="button"
                    className="cursor-pointer text-primary underline"
                    onClick={() => setShowPage((v) => !v)}
                  >
                    {showPage ? '접기' : '교안 보기'}
                  </button>
                </>
              )}
            </div>
          )}
        </blockquote>
      )}
      {showPage && (
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md border bg-card p-3 text-xs">
          {page.data?.text ?? '불러오는 중…'}
        </pre>
      )}
      <div className="flex flex-col gap-1">
        {result.mastery.map((m) => (
          <div key={m.concept_id} className="flex justify-between text-xs">
            <span>{m.name}</span>
            <span className="text-muted-foreground">
              숙련도 {pct(m.before)} → <b className="text-foreground">{pct(m.after)}</b>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
