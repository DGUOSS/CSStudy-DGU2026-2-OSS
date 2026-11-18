import { pct } from '@/features/mastery/queries'
import { SectionHeader } from './SectionHeader'

type Totals = { attempts: number; wrong: number; accuracy: number | null }

export function Stats({ totals }: { totals: Totals }) {
  const items = [
    { label: '푼 문제 (누적)', value: String(totals.attempts) },
    { label: '정답률', value: totals.accuracy === null ? '-' : pct(totals.accuracy) },
    { label: '틀린 횟수 (누적)', value: String(totals.wrong) },
  ]
  return (
    <section className="flex flex-col gap-3.5">
      <SectionHeader title="학습 현황" />
      <div className="grid grid-cols-3 gap-3.5">
        {items.map((it) => (
          <div key={it.label} className="rounded-2xl border border-home-line bg-white p-5">
            <div className="text-4xl leading-tight font-bold">{it.value}</div>
            <p className="mt-1.5 text-sm text-ink-2">{it.label}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
