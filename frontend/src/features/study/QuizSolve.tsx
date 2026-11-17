import { useMutation, useQuery } from '@tanstack/react-query'
import { Check, ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useState } from 'react'
import { api, unwrap } from '@/api/client'
import { ErrorText } from '@/components/States'
import { pct } from '@/features/mastery/queries'
import { cn } from '@/lib/utils'
import { emptyEntries, type Entry, type Problem, type Result, statusOf } from './quizTypes'

/** 풀이 화면: 문제 번호로 아무 문제나 오갈 수 있고, 건너뛰기·정답 확인을 한다. */
export function QuizSolve({
  problems,
  onFinish,
}: {
  problems: Problem[]
  onFinish: (entries: Entry[]) => void
}) {
  const [entries, setEntries] = useState<Entry[]>(() => emptyEntries(problems))
  const [cur, setCur] = useState(0)
  const last = problems.length - 1
  const entry = entries[cur]
  const problem = problems[cur]

  const patch = (i: number, p: Partial<Entry>, base = entries) =>
    base.map((e, j) => (j === i ? { ...e, ...p } : e))
  const unresolved = (list: Entry[]) => list.map((e, i) => (statusOf(e) === 'open' ? i : -1)).filter((i) => i >= 0)

  /** 다음 문제로. 마지막이면 안 푼 문제로 돌아가고, 전부 끝났으면 결과로 간다. */
  const goNext = (list: Entry[]) => {
    if (cur < last) return setCur(cur + 1)
    const rest = unresolved(list)
    if (rest.length === 0) return onFinish(list)
    setCur(rest[0])
  }

  const submit = useMutation({
    mutationFn: ({ index, chosen }: { index: number; chosen: number }) =>
      unwrap(
        api.POST('/api/v1/problems/{problem_id}/attempts', {
          params: { path: { problem_id: problems[index].id } },
          body: { chosen_index: chosen },
        }),
      ),
    onSuccess: (result, { index }) =>
      setEntries((cur) => patch(index, { result, skipped: false }, cur)),
  })

  const choose = (i: number) => {
    if (entry.result || submit.isPending) return
    setEntries(patch(cur, { chosen: i }))
  }
  const skip = () => {
    const next = patch(cur, { skipped: true, chosen: null })
    setEntries(next)
    goNext(next)
  }
  const allResolved = unresolved(entries).length === 0

  return (
    <>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">퀴즈 풀이</h1>
          <p className="mt-1 text-sm text-ink-2">
            {cur + 1} / {problems.length}
          </p>
        </div>
        <button
          type="button"
          disabled={!allResolved}
          onClick={() => onFinish(entries)}
          title={allResolved ? '' : '모든 문제를 풀거나 건너뛰면 결과를 볼 수 있어요'}
          className="h-10 cursor-pointer rounded-full border border-navy px-5 text-sm font-bold text-navy hover:bg-navy-tint disabled:cursor-not-allowed disabled:opacity-40"
        >
          결과 보기
        </button>
      </header>

      <span className="h-1.5 w-full overflow-hidden rounded-full bg-[#e6eaf2]">
        <span
          className="block h-full rounded-full bg-navy transition-all"
          style={{ width: `${((cur + 1) / problems.length) * 100}%` }}
        />
      </span>

      <Navigator entries={entries} cur={cur} onJump={setCur} />

      <section className="flex flex-col gap-5 rounded-2xl border border-home-line bg-white p-6">
        <div className="flex flex-wrap items-center gap-1.5">
          {problem.concepts.map((c) => (
            <span key={c.id} className="rounded-md bg-navy-tint px-2 py-0.5 text-xs font-medium text-navy">
              {c.name}
            </span>
          ))}
          {problem.origin === 'sample' && (
            <span className="rounded-md border border-home-line px-2 py-0.5 text-xs text-ink-2">
              샘플 문제
            </span>
          )}
          {entry.skipped && !entry.result && (
            <span className="rounded-md bg-gold-soft px-2 py-0.5 text-xs font-bold">건너뜀</span>
          )}
        </div>
        <p className="text-lg leading-relaxed font-bold whitespace-pre-wrap">{problem.question}</p>

        <div className="flex flex-col gap-2.5">
          {problem.choices.map((choice, i) => {
            const result = entry.result
            const isAnswer = !!result && i === result.answer_index
            const isWrongPick = !!result && i === entry.chosen && !result.correct
            const picked = !result && entry.chosen === i
            return (
              <button
                key={choice}
                type="button"
                onClick={() => choose(i)}
                disabled={!!result || submit.isPending}
                className={cn(
                  'flex items-start gap-3 rounded-xl border px-4 py-3.5 text-left transition-colors',
                  !result && 'cursor-pointer hover:bg-home-bg',
                  picked && 'border-navy bg-navy-tint',
                  !picked && !isAnswer && !isWrongPick && 'border-home-line',
                  isAnswer && 'border-[#2e8b6a] bg-[#e8f4ef]',
                  isWrongPick && 'border-[#c8453f] bg-[#fbeceb]',
                )}
              >
                <span
                  className={cn(
                    'mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-bold',
                    picked ? 'bg-navy text-white' : 'bg-home-bg text-ink-2',
                  )}
                >
                  {i + 1}
                </span>
                <span className="flex-1 font-mono text-sm whitespace-pre-wrap">{choice}</span>
                {isAnswer && <Check size={18} className="text-[#2e8b6a]" />}
                {isWrongPick && <X size={18} className="text-[#c8453f]" />}
              </button>
            )
          })}
        </div>
        <ErrorText error={submit.error} />
        {entry.result && <Explanation result={entry.result} />}
      </section>

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={cur === 0}
          onClick={() => setCur(cur - 1)}
          className="inline-flex h-11 cursor-pointer items-center gap-1 rounded-full border border-home-line bg-white px-5 text-[15px] font-bold disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeft size={16} />
          이전
        </button>
        <span className="flex-1" />
        {entry.result ? (
          <button
            type="button"
            onClick={() => goNext(entries)}
            className="inline-flex h-11 cursor-pointer items-center gap-1 rounded-full bg-navy px-6 text-[15px] font-bold text-white hover:bg-navy-deep"
          >
            {cur === last && allResolved ? '결과 보기' : '다음 문제'}
            <ChevronRight size={16} />
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={skip}
              className="inline-flex h-11 cursor-pointer items-center gap-1 rounded-full bg-gold-soft px-5 text-[15px] font-bold hover:bg-gold"
            >
              건너뛰기
              <ChevronRight size={16} />
            </button>
            <button
              type="button"
              disabled={entry.chosen === null || submit.isPending}
              onClick={() => submit.mutate({ index: cur, chosen: entry.chosen as number })}
              className="h-11 cursor-pointer rounded-full bg-navy px-6 text-[15px] font-bold text-white hover:bg-navy-deep disabled:cursor-not-allowed disabled:opacity-40"
            >
              {submit.isPending ? '채점 중…' : '정답 확인'}
            </button>
          </>
        )}
      </div>
    </>
  )
}

function Navigator({
  entries,
  cur,
  onJump,
}: {
  entries: Entry[]
  cur: number
  onJump: (i: number) => void
}) {
  return (
    <nav aria-label="문제 번호" className="flex flex-wrap gap-2">
      {entries.map((e, i) => {
        const st = statusOf(e)
        return (
          <button
            key={i}
            type="button"
            onClick={() => onJump(i)}
            aria-current={i === cur ? 'step' : undefined}
            title={{ correct: '정답', wrong: '오답', skipped: '건너뜀', open: '안 푼 문제' }[st]}
            className={cn(
              'flex size-10 cursor-pointer items-center justify-center rounded-full border text-sm font-bold',
              i === cur && 'border-navy bg-navy text-white',
              i !== cur && st === 'correct' && 'border-[#2e8b6a] bg-[#e8f4ef] text-[#2e8b6a]',
              i !== cur && st === 'wrong' && 'border-[#c8453f] bg-[#fbeceb] text-[#c8453f]',
              i !== cur && st === 'skipped' && 'border-gold bg-gold-soft',
              i !== cur && st === 'open' && 'border-home-line bg-white text-ink-2',
            )}
          >
            {i + 1}
          </button>
        )
      })}
    </nav>
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
    <div className="flex flex-col gap-3 rounded-xl bg-gold-soft/60 p-4 text-sm">
      <div className={cn('font-bold', result.correct ? 'text-[#2e8b6a]' : 'text-[#c8453f]')}>
        {result.correct ? '정답입니다' : `오답입니다 · 정답 ${result.answer_index + 1}번`}
      </div>
      <p className="leading-relaxed whitespace-pre-wrap">{result.explanation}</p>
      {result.evidence && (
        <blockquote className="border-l-2 border-navy pl-3 text-ink-2">
          {result.evidence}
          {source && (
            <span className="mt-1 block text-xs">
              — {source.title}
              {source.page && (
                <>
                  {' '}
                  {source.page}쪽{' '}
                  <button
                    type="button"
                    className="cursor-pointer font-bold text-navy underline"
                    onClick={() => setShowPage((v) => !v)}
                  >
                    {showPage ? '접기' : '교안 보기'}
                  </button>
                </>
              )}
            </span>
          )}
        </blockquote>
      )}
      {showPage && (
        <pre className="max-h-64 overflow-auto rounded-md border border-home-line bg-white p-3 text-xs whitespace-pre-wrap">
          {page.data?.text ?? '불러오는 중…'}
        </pre>
      )}
      <div className="flex flex-col gap-1">
        {result.mastery.map((m) => (
          <div key={m.concept_id} className="flex justify-between text-xs">
            <span>{m.name}</span>
            <span className="text-ink-2">
              숙련도 {pct(m.before)} → <b className="text-ink">{pct(m.after)}</b>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
