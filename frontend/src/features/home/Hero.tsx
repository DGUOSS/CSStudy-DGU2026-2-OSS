import { ArrowUpRight, ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { cn } from '@/lib/utils'
import { pct } from '@/features/mastery/queries'
import { subjectIcon } from '@/features/study/subjectIcon'
import type { SubjectSummary } from './queries'

const TONES = ['bg-tone-blue', 'bg-tone-gold', 'bg-tone-gray']

export function Hero({
  userName,
  subjects,
  loading,
}: {
  userName: string
  subjects: SubjectSummary[]
  loading: boolean
}) {
  // 과목이 많으면 3개씩 끊어서 보여 주고, 화살표를 누르면 다음 3개로 넘어간다
  const PER = 3
  const pages = Math.max(1, Math.ceil(subjects.length / PER))
  const [rawPage, setPage] = useState(0)
  const page = Math.min(rawPage, pages - 1) // 과목 수가 줄어도 빈 쪽이 안 보이게
  const shown = subjects.slice(page * PER, page * PER + PER)
  // 양옆 화살표: 배경 없이 얇게. 끝 쪽에서는 자리만 남기고 숨긴다(카드 위치가 흔들리지 않게)
  const arrow =
    'flex w-6 shrink-0 cursor-pointer items-center justify-center self-stretch rounded-md text-white/60 hover:text-white disabled:invisible'
  return (
    <section className="flex flex-col gap-6 rounded-3xl bg-navy-deep p-8 lg:flex-row">
      <div className="flex flex-col justify-between gap-6 lg:w-[250px] lg:shrink-0">
        <h1 className="text-xl leading-snug font-medium text-white">
          {userName}님,
          <br />
          학습을 시작해 볼까요?
        </h1>
        <Link
          to="/study"
          className="inline-flex h-11 w-fit items-center gap-2 rounded-full bg-white px-5 text-[15px] font-bold text-navy hover:bg-navy-tint"
        >
          학습하러 가기
          <ArrowUpRight size={16} strokeWidth={2.4} />
        </Link>
      </div>

      {loading ? (
        <p className="flex-1 self-center text-sm text-white/70">과목 불러오는 중…</p>
      ) : shown.length === 0 ? (
        <p className="flex-1 self-center text-sm text-white/80">
          아직 내 과목이 없습니다. &lsquo;학습하러 가기&rsquo;에서 과목을 추가해 주세요.
        </p>
      ) : (
        <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex min-w-0 items-stretch gap-1.5">
        {pages > 1 && (
          <button type="button" aria-label="이전 과목" disabled={page === 0} onClick={() => setPage(page - 1)} className={arrow}>
            <ChevronLeft size={22} strokeWidth={1.6} aria-hidden="true" />
          </button>
        )}
        <div className="grid min-w-0 flex-1 grid-cols-1 gap-4 sm:grid-cols-3" aria-live="polite">
          {shown.map((s, i) => {
            const { Icon } = subjectIcon(s.name, 0)
            return (
            <Link
              key={s.key}
              to="/study"
              className={cn(
                'flex min-w-0 flex-col rounded-[18px] p-[18px] transition hover:-translate-y-0.5',
                TONES[(page * PER + i) % TONES.length],
              )}
            >
              <span className="flex size-10 items-center justify-center rounded-xl bg-white text-navy">
                <Icon size={22} strokeWidth={1.8} aria-hidden="true" />
              </span>
              <span className="mt-4 truncate text-lg font-bold">{s.name}</span>
              <span className="mt-3 text-[13px] text-ink-2">
                강좌 {s.courseCount}개 | 숙련도 {pct(s.mastery)}
              </span>
              <span className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-white/70">
                <span
                  className="block h-full rounded-full bg-navy-deep"
                  style={{ width: `${Math.round(s.mastery * 100)}%` }}
                />
              </span>
            </Link>
            )
          })}
        </div>
        {pages > 1 && (
          <button type="button" aria-label="다음 과목" disabled={page === pages - 1} onClick={() => setPage(page + 1)} className={arrow}>
            <ChevronRight size={22} strokeWidth={1.6} aria-hidden="true" />
          </button>
        )}
        </div>
        {pages > 1 && (
          <div className="flex justify-center gap-2" role="group" aria-label="과목 쪽">
            {Array.from({ length: pages }, (_, i) => (
              <button
                key={i}
                type="button"
                aria-label={`${i + 1}쪽`}
                aria-current={i === page}
                onClick={() => setPage(i)}
                className={cn(
                  'h-1.5 cursor-pointer rounded-full transition-all',
                  i === page ? 'w-4 bg-white' : 'w-1.5 bg-white/35 hover:bg-white/60',
                )}
              />
            ))}
          </div>
        )}
        </div>
      )}
    </section>
  )
}
