import type { Schemas } from '@/api/client'

/** 관리자: 강의계획서 판정 결과 한 줄 */
export function SyllabusResult({ r }: { r: Schemas['SyllabusImportOut'] | null }) {
  if (!r) return null
  return (
    <p>
      강의계획서 {r.checked}건 판정: 팀플 있음 {r.yes}, 없음 {r.no}, 언급 없음 {r.not_mentioned}
      {r.missing > 0 && ` (개설 목록에 없어 건너뜀 ${r.missing}건)`}
    </p>
  )
}
