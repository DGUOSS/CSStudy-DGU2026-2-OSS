import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router'

/**
 * '이전 화면으로': 들어온 화면으로 돌아간다(홈·강좌·스터디 모음 등 어디서 왔든).
 * 주소를 직접 치고 들어와 돌아갈 곳이 없으면 fallback으로 간다.
 */
export function BackButton({ fallback, label = '이전 화면으로' }: { fallback: string; label?: string }) {
  const nav = useNavigate()
  return (
    <button
      type="button"
      onClick={() => {
        // react-router는 이 앱 안에서 쌓인 기록 순번을 history.state.idx에 둔다. 0이면 이 앱의 첫 화면
        const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0
        if (idx > 0) nav(-1)
        else nav(fallback)
      }}
      className="inline-flex w-fit cursor-pointer items-center gap-1 text-sm text-ink-2 hover:text-navy"
    >
      <ArrowLeft size={15} aria-hidden="true" /> {label}
    </button>
  )
}
