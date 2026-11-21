import { Users } from 'lucide-react'
import type { Schemas } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { teamSourceText } from './teamText'

type TeamLabel = Schemas['TeamLabelOut']

const TEXT: Record<string, string> = {
  yes: '팀플 있음',
  no: '팀플 없음',
  likely_no: '팀플 언급 없음',
}

const TONE: Record<string, string> = {
  yes: 'border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-200',
  no: 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200',
  likely_no: 'text-muted-foreground',
}

/** 팀플 라벨 배지. 정보가 없으면(unknown) 아무것도 그리지 않는다. */
export function TeamBadge({ label, showTerm = false, className }: {
  label: TeamLabel | null | undefined
  showTerm?: boolean
  className?: string
}) {
  if (!label || !TEXT[label.label]) return null
  return (
    <Badge
      variant="outline"
      className={cn('gap-1', TONE[label.label], className)}
      title={teamSourceText(label)}
    >
      <Users aria-hidden="true" className="size-3" />
      {TEXT[label.label]}
      {label.differs_from_syllabus && <span className="font-normal opacity-80">· 계획서와 다름</span>}
      {showTerm && <span className="font-normal opacity-80">· {label.term}</span>}
    </Badge>
  )
}
