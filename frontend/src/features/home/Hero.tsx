import { ArrowUpRight, BookOpen } from 'lucide-react'
import { Link } from 'react-router'
import { cn } from '@/lib/utils'
import { pct } from '@/features/mastery/queries'
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
  const shown = subjects.slice(0, 3)
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
        <div className="grid flex-1 grid-cols-1 gap-4 sm:grid-cols-3">
          {shown.map((s, i) => (
            <Link
              key={s.key}
              to="/study"
              className={cn(
                'flex min-w-0 flex-col rounded-[18px] p-[18px] transition hover:-translate-y-0.5',
                TONES[i % TONES.length],
              )}
            >
              <span className="flex size-10 items-center justify-center rounded-xl bg-white text-navy">
                <BookOpen size={22} strokeWidth={1.8} />
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
          ))}
        </div>
      )}
    </section>
  )
}
