/** 고른 오답에 붙여 둔 오개념: "이 보기를 고른 사람은 보통 이렇게 생각합니다". 문제 풀이 두 화면에서 같이 쓴다. */
import { Lightbulb } from 'lucide-react'
import type { Schemas } from '@/api/client'

export function MisconceptionNote({
  misconception: m,
}: {
  misconception: Schemas['AttemptMisconception'] | null | undefined
}) {
  if (!m) return null
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-amber-300/70 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-100">
      <div className="flex flex-wrap items-center gap-2 font-semibold">
        <Lightbulb size={16} aria-hidden="true" />
        이 보기를 고른 이유일 수 있어요
        <span className="rounded-full bg-amber-200/70 px-2 py-0.5 text-xs font-medium dark:bg-amber-800/50">
          {m.status === 'approved' ? '확인된 오개념' : 'AI 추정'}
        </span>
      </div>
      <p className="font-medium">{m.label}</p>
      <p className="leading-relaxed">{m.hypothesis}</p>
      <p className="leading-relaxed text-amber-900/80 dark:text-amber-100/80">{m.explanation}</p>
      {m.source?.page && (
        <p className="text-xs text-amber-900/70 dark:text-amber-100/70">
          다시 볼 곳: {m.source.title} {m.source.page}쪽
        </p>
      )}
    </div>
  )
}
