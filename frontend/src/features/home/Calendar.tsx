import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { cn } from '@/lib/utils'

const WEEK = ['일', '월', '화', '수', '목', '금', '토']
const key = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** eventDates: 'YYYY-MM-DD' 모음. 날짜 아래에 골드 점이 찍힌다. */
export function Calendar({ today, eventDates }: { today: Date; eventDates: Set<string> }) {
  const [cursor, setCursor] = useState(new Date(today.getFullYear(), today.getMonth(), 1))

  const cells = useMemo(() => {
    const y = cursor.getFullYear()
    const m = cursor.getMonth()
    const lead = new Date(y, m, 1).getDay()
    const total = Math.ceil((lead + new Date(y, m + 1, 0).getDate()) / 7) * 7
    return Array.from({ length: total }, (_, i) => {
      const date = new Date(y, m, 1 - lead + i)
      return { date, inMonth: date.getMonth() === m }
    })
  }, [cursor])

  const move = (n: number) => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + n, 1))

  return (
    <section className="rounded-[20px] border border-home-line bg-white p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">
          {cursor.getFullYear()}년 {cursor.getMonth() + 1}월
        </h2>
        <div className="flex gap-3">
          <button type="button" aria-label="이전 달" onClick={() => move(-1)} className="cursor-pointer rounded hover:bg-home-bg">
            <ChevronLeft size={20} />
          </button>
          <button type="button" aria-label="다음 달" onClick={() => move(1)} className="cursor-pointer rounded hover:bg-home-bg">
            <ChevronRight size={20} />
          </button>
        </div>
      </div>

      <div className="mt-3.5 grid grid-cols-7 text-center text-[13px] text-ink-2">
        {WEEK.map((w) => (
          <span key={w} className="py-1">
            {w}
          </span>
        ))}
      </div>

      <div className="mt-3.5 grid grid-cols-7 gap-y-3.5 text-center text-sm">
        {cells.map(({ date, inMonth }) => {
          const isToday = key(date) === key(today)
          return (
            <div
              key={key(date)}
              className={cn(
                'relative flex h-10 items-center justify-center rounded-xl',
                isToday ? 'bg-navy font-bold text-white' : inMonth ? '' : 'text-ink-2/50',
              )}
            >
              {date.getDate()}
              {inMonth && eventDates.has(key(date)) && (
                <span className="absolute bottom-2 size-[5px] rounded-full bg-gold" />
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
