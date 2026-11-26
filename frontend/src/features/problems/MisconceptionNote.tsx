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
    <div className="flex flex-col gap-1.5 rounded-xl border border-gold/60 bg-[#fdf6e7] p-4 text-sm text-[#4a3407]">
      <div className="flex flex-wrap items-center gap-2 font-bold">
        <Lightbulb size={16} aria-hidden="true" />
        이 보기를 고른 이유일 수 있어요
        <span className="rounded-full bg-gold-soft px-2.5 py-0.5 text-xs font-bold text-[#6b4a0c]">
          {m.status === 'approved' ? '확인된 오개념' : 'AI 추정'}
        </span>
      </div>
      <p className="font-medium">{m.label}</p>
      <p className="leading-relaxed">{m.hypothesis}</p>
      <p className="leading-relaxed text-[#6b4a0c]">{m.explanation}</p>
      {m.source?.page && (
        <p className="text-xs font-bold text-[#6b4a0c]">
          다시 볼 곳: {m.source.title} {m.source.page}쪽
        </p>
      )}
    </div>
  )
}
