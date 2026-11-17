import { CalendarDays, FileText } from 'lucide-react'
import { Empty } from '@/components/States'
import { SectionHeader } from './SectionHeader'
import type { DeadlineItem } from './queries'

const DAY = 86_400_000
const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
const dday = (due: string, now: Date) => {
  const n = Math.round((startOfDay(new Date(due)) - startOfDay(now)) / DAY)
  return n === 0 ? 'D-Day' : n > 0 ? `D-${n}` : `D+${-n}`
}
const fmtDate = (due: string) => {
  const d = new Date(due)
  return `${d.getMonth() + 1}월 ${d.getDate()}일`
}
const fmtTime = (due: string) => {
  const d = new Date(due)
  return `${fmtDate(due)} · ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** 앞으로 7일 안의 시험·과제 */
export function WeekDeadlines({ items, now }: { items: DeadlineItem[]; now: Date }) {
  const week = items.filter((d) => {
    const diff = startOfDay(new Date(d.due)) - startOfDay(now)
    return diff >= 0 && diff <= 7 * DAY
  })
  return (
    <section className="flex flex-col gap-3.5">
      <SectionHeader title="이번 주 시험 과제" />
      {week.length === 0 ? (
        <Empty>이번 주 시험·과제 일정이 없습니다.</Empty>
      ) : (
        <ul className="overflow-hidden rounded-2xl border border-home-line bg-white">
          {week.map((d) => (
            <li
              key={d.id}
              className="flex items-center gap-4 border-b border-home-line px-5 py-4 last:border-b-0"
            >
              <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-tone-blue text-navy">
                <FileText size={22} strokeWidth={1.8} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-bold">{d.title}</p>
                <p className="truncate text-sm text-ink-2">{d.courseName}</p>
              </div>
              <span className="text-sm text-ink-2">{fmtDate(d.due)}</span>
              <span className="rounded-xl bg-gold-soft px-2.5 py-1 text-sm font-bold">
                {dday(d.due, now)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function Upcoming({ items, now }: { items: DeadlineItem[]; now: Date }) {
  const next = items
    .filter((d) => startOfDay(new Date(d.due)) >= startOfDay(now))
    .sort((a, b) => a.due.localeCompare(b.due))
    .slice(0, 3)
  return (
    <section className="flex flex-col gap-3.5">
      <SectionHeader title="다가오는 일정" />
      {next.length === 0 ? (
        <Empty>다가오는 일정이 없습니다.</Empty>
      ) : (
        <ul className="overflow-hidden rounded-2xl border border-home-line bg-white">
          {next.map((d) => (
            <li
              key={d.id}
              className="flex items-center gap-3.5 border-b border-home-line px-4 py-3.5 last:border-b-0"
            >
              <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-navy text-gold">
                <CalendarDays size={22} strokeWidth={1.8} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] text-ink-2">{fmtTime(d.due)}</span>
                <span className="block truncate text-[15px] font-bold">{d.title}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
