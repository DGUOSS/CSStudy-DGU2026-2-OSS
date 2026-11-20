import { Users } from 'lucide-react'
import type { Schemas } from '@/api/client'
import { cn } from '@/lib/utils'
import { teamSourceText } from './teamText'

type History = Schemas['TeamHistoryOut']

const SUMMARY: Record<string, string> = {
  yes: '팀플 있음',
  no: '팀플 없음',
  likely_no: '팀플 언급 없음',
  mixed: '학기마다 다름',
}
const TERM_TEXT: Record<string, string> = { yes: '있음', no: '없음', likely_no: '언급 없음', unknown: '모름' }
const TONE: Record<string, string> = {
  yes: 'border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-200',
  no: 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200',
  mixed: 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200',
  likely_no: 'text-muted-foreground',
  unknown: 'text-muted-foreground',
}

/** "2026 2학기" → "26-2", 여름·겨울은 "26-여름" */
function shortTerm(t: Schemas['TeamLabelOut']) {
  const sem = { 'CM160.10': '1', 'CM160.20': '2', 'CM160.11': '여름', 'CM160.21': '겨울' }[t.sem_cd] ?? t.sem_cd
  return `${t.year.slice(2)}-${sem}`
}

/**
 * 같은 교수·같은 과목의 최근 3개 연도 팀플 기록. 수강신청 전에 보는 용도.
 * 요약 배지 + 학기별 칸. 기록이 하나도 없으면 그리지 않는다.
 */
export function TeamYears({ history, className }: { history: History | null | undefined; className?: string }) {
  if (!history || history.terms.length === 0 || history.summary === 'unknown') return null
  const range = history.from_year === history.to_year ? history.to_year : `${history.from_year}~${history.to_year}`
  return (
    <div className={cn('flex flex-wrap items-center gap-1.5 text-xs', className)}>
      <span
        className={cn('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-medium', TONE[history.summary])}
        title={`${range}년, 이 교수 수업 기준`}
      >
        <Users aria-hidden="true" className="size-3" />
        최근 3년 {SUMMARY[history.summary]}
      </span>
      <ul className="flex flex-wrap gap-1" aria-label="학기별 팀플">
        {history.terms.map((t) => (
          <li
            key={`${t.year}-${t.sem_cd}`}
            title={teamSourceText(t)}
            className={cn('rounded border px-1.5 py-0.5', TONE[t.label])}
          >
            {shortTerm(t)} {TERM_TEXT[t.label] ?? t.label}
            {t.differs_from_syllabus && <span className="opacity-80"> (계획서와 다름)</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}
