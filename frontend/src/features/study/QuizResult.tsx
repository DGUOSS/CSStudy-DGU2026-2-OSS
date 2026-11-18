import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { useMastery, pct } from '@/features/mastery/queries'
import { cn } from '@/lib/utils'
import { type Entry, type Problem, statusOf } from './quizTypes'
import { useChapters } from './queries'

type Weak = { id: number; name: string; chapterId: number; mastery: number; wrong: number; skipped: number }

/** 결과 화면: 정답률, 취약점 정리, 틀린·건너뛴 문제 복습, 맞힌 문제 목록 */
export function QuizResult({
  courseId,
  problems,
  entries,
  onRetry,
  onRestart,
}: {
  courseId: number
  problems: Problem[]
  entries: Entry[]
  onRetry: (problems: Problem[]) => void
  onRestart: () => void
}) {
  const mastery = useMastery(courseId)
  const chapters = useChapters(courseId)
  const [showCorrect, setShowCorrect] = useState(false)

  const rows = problems.map((p, i) => ({ p, e: entries[i], i, st: statusOf(entries[i]) }))
  const correct = rows.filter((r) => r.st === 'correct')
  const wrong = rows.filter((r) => r.st === 'wrong')
  const skipped = rows.filter((r) => r.st === 'skipped' || r.st === 'open')
  const review = rows.filter((r) => r.st !== 'correct')
  const chapterTitle = (id: number) => chapters.data?.find((c) => c.id === id)?.title ?? ''

  // 취약점: 틀리거나 건너뛴 문제의 개념. 숙련도가 낮은 순으로 3개
  const known = new Map(
    (mastery.data ?? []).flatMap((ch) => ch.concepts.map((c) => [c.concept_id, c.mastery] as const)),
  )
  const weak = new Map<number, Weak>()
  for (const r of review) {
    for (const c of r.p.concepts) {
      const now = r.e.result?.mastery.find((m) => m.concept_id === c.id)?.after ?? known.get(c.id) ?? 0
      const w = weak.get(c.id) ?? {
        id: c.id,
        name: c.name,
        chapterId: r.p.chapter_id,
        mastery: now,
        wrong: 0,
        skipped: 0,
      }
      if (r.st === 'wrong') w.wrong += 1
      else w.skipped += 1
      weak.set(c.id, w)
    }
  }
  const weakList = [...weak.values()].sort((a, b) => a.mastery - b.mastery).slice(0, 3)

  const tiles = [
    { label: '정답률', value: pct(correct.length / problems.length), navy: true },
    { label: '정답', value: String(correct.length), color: 'text-[#2e8b6a]' },
    { label: '오답', value: String(wrong.length), color: 'text-[#c8453f]' },
    { label: '건너뜀', value: String(skipped.length) },
  ]

  return (
    <>
      <header>
        <h1 className="text-2xl font-bold">퀴즈 결과</h1>
        <p className="mt-1 text-sm text-ink-2">{problems.length}문제</p>
      </header>

      <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-4">
        {tiles.map((t) => (
          <div
            key={t.label}
            className={cn(
              'rounded-2xl border p-5',
              t.navy ? 'border-navy bg-navy text-white' : 'border-home-line bg-white',
            )}
          >
            <p className={cn('text-sm', t.navy ? 'text-white/80' : 'text-ink-2')}>{t.label}</p>
            <p className={cn('mt-1 text-3xl font-bold', t.color)}>{t.value}</p>
          </div>
        ))}
      </div>

      {weakList.length > 0 && (
        <section className="flex flex-col gap-4 rounded-2xl border border-home-line bg-white p-6">
          <div>
            <h2 className="text-lg font-bold">취약점 정리</h2>
            <p className="mt-1 text-sm text-ink-2">
              틀리거나 건너뛴 문제에 들어 있던 개념이에요. 숙련도가 낮은 순서로 보여 줘요.
            </p>
          </div>
          <ul className="flex flex-col gap-4">
            {weakList.map((w) => (
              <li key={w.id} className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <div className="min-w-0 flex-1 basis-40">
                  <p className="font-bold">{w.name}</p>
                  <p className="text-xs text-ink-2">
                    {chapterTitle(w.chapterId)}
                    {w.wrong > 0 && ` · 오답 ${w.wrong}`}
                    {w.skipped > 0 && ` · 건너뜀 ${w.skipped}`}
                  </p>
                </div>
                <span className="h-2 w-32 overflow-hidden rounded-full bg-[#e6eaf2]">
                  <span
                    className="block h-full rounded-full bg-navy"
                    style={{ width: `${Math.round(w.mastery * 100)}%` }}
                  />
                </span>
                <span className="w-10 text-sm font-bold">{pct(w.mastery)}</span>
                <span className="rounded-xl bg-gold-soft px-2.5 py-1 text-xs font-bold">복습 필요</span>
                <Link
                  to={`/study/courses/${courseId}/quiz?chapters=${w.chapterId}`}
                  className="rounded-full border border-navy px-4 py-1.5 text-sm font-bold text-navy hover:bg-navy-tint"
                >
                  이 챕터 풀기
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {review.length > 0 && (
        <section className="flex flex-col gap-3.5">
          <h2 className="text-xl font-bold">
            틀린 문제 · 건너뛴 문제 <span className="text-ink-2">{review.length}</span>
          </h2>
          {review.map(({ p, e, i, st }) => (
            <article key={p.id} className="flex flex-col gap-4 rounded-2xl border border-home-line bg-white p-6">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span
                  className={cn(
                    'flex size-7 items-center justify-center rounded-full border font-bold',
                    st === 'wrong'
                      ? 'border-[#c8453f] text-[#c8453f]'
                      : 'border-gold bg-gold-soft',
                  )}
                >
                  {i + 1}
                </span>
                {p.concepts[0] && (
                  <span className="rounded-md bg-navy-tint px-2 py-0.5 text-xs font-medium text-navy">
                    {p.concepts[0].name}
                  </span>
                )}
                <span className={cn('font-bold', st === 'wrong' ? 'text-[#c8453f]' : 'text-ink-2')}>
                  {st === 'wrong' ? '오답' : '건너뜀'}
                </span>
              </div>
              <p className="font-bold whitespace-pre-wrap">{p.question}</p>
              {st === 'wrong' && e.result ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-[#c8453f]/40 bg-[#fbeceb] p-4">
                      <p className="text-xs font-bold text-[#c8453f]">내 답</p>
                      <p className="mt-1 font-mono text-sm whitespace-pre-wrap">
                        {(e.chosen ?? 0) + 1}번 {p.choices[e.chosen ?? 0]}
                      </p>
                    </div>
                    <div className="rounded-xl border border-[#2e8b6a]/40 bg-[#e8f4ef] p-4">
                      <p className="text-xs font-bold text-[#2e8b6a]">정답</p>
                      <p className="mt-1 font-mono text-sm whitespace-pre-wrap">
                        {e.result.answer_index + 1}번 {p.choices[e.result.answer_index]}
                      </p>
                    </div>
                  </div>
                  <p className="rounded-xl bg-gold-soft/70 p-4 text-sm leading-relaxed whitespace-pre-wrap">
                    {e.result.explanation}
                  </p>
                </>
              ) : (
                <p className="rounded-xl bg-home-bg p-4 text-sm text-ink-2">
                  답하지 않고 건너뛴 문제예요. 다시 풀면 정답과 해설을 볼 수 있어요.
                </p>
              )}
            </article>
          ))}
        </section>
      )}

      {correct.length > 0 && (
        <section className="flex flex-col gap-3">
          <button
            type="button"
            onClick={() => setShowCorrect((v) => !v)}
            aria-expanded={showCorrect}
            className="flex cursor-pointer items-center justify-between rounded-2xl border border-home-line bg-white px-6 py-4 text-left font-bold"
          >
            맞힌 문제 {correct.length}개 {showCorrect ? '접기' : '보기'}
            <ChevronDown size={18} className={cn('transition-transform', showCorrect && 'rotate-180')} />
          </button>
          {showCorrect && (
            <ul className="divide-y divide-home-line rounded-2xl border border-home-line bg-white px-6">
              {correct.map(({ p, e, i }) => (
                <li key={p.id} className="flex items-center gap-4 py-4">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-[#2e8b6a] text-sm font-bold text-[#2e8b6a]">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-bold">{p.question}</p>
                    <p className="truncate text-xs text-ink-2">
                      {chapterTitle(p.chapter_id)} | 내 답 {p.choices[e.chosen ?? 0]}
                    </p>
                  </div>
                  <span className="shrink-0 text-sm font-bold text-[#2e8b6a]">정답 ✓</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to={`/study/courses/${courseId}`}
          className="inline-flex h-11 items-center rounded-full border border-home-line bg-white px-5 text-[15px] font-bold"
        >
          단원 선택으로
        </Link>
        {review.length > 0 ? (
          <button
            type="button"
            onClick={() => onRetry(review.map((r) => r.p))}
            className="h-11 cursor-pointer rounded-full bg-navy px-6 text-[15px] font-bold text-white hover:bg-navy-deep"
          >
            틀린·건너뛴 {review.length}문제 다시 풀기
          </button>
        ) : (
          <button
            type="button"
            onClick={onRestart}
            className="h-11 cursor-pointer rounded-full bg-navy px-6 text-[15px] font-bold text-white hover:bg-navy-deep"
          >
            새 문제 풀기
          </button>
        )}
      </div>
    </>
  )
}
