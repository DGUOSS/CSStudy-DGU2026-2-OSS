import { Bookmark, ExternalLink } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { ErrorText } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useAuth } from '@/features/auth/useAuth'
import {
  bookmarkletHref,
  MESSAGE_TYPE,
  NDRIMS_ORIGINS,
  NDRIMS_URL,
  type NdrimsPayload,
} from './bookmarklet'
import { useImportNdrims } from './queries'

/**
 * 엔드림스 수강 기록 가져오기 안내.
 * ① 즐겨찾기 버튼 끌어다 놓기 → ② 엔드림스 열기 → ③ 직접 로그인, 즐겨찾기 누르기, 화면 열기 → ④ 보내기
 */
export function ImportPanel({ compact = false }: { compact?: boolean }) {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const save = useImportNdrims(isAdmin)
  const linkRef = useRef<HTMLAnchorElement>(null)

  // React는 javascript: 주소를 막으므로 직접 넣는다
  useEffect(() => {
    linkRef.current?.setAttribute('href', bookmarkletHref(window.location.origin))
  }, [])

  // 엔드림스 창에서 보낸 기록을 받는다
  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (!NDRIMS_ORIGINS.includes(e.origin)) return
      const d = e.data as NdrimsPayload
      if (d?.type !== MESSAGE_TYPE) return
      // 받았다고 알려 준다. 답이 없으면 엔드림스 창은 새 탭으로 보낸다
      ;(e.source as Window | null)?.postMessage({ type: MESSAGE_TYPE + '-ack' }, e.origin)
      save.mutate(d)
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [save])

  const r = save.data
  return (
    <Card className="flex flex-col gap-5 p-5">
      {!compact && (
        <div>
          <h2 className="text-lg font-semibold">엔드림스에서 수강 기록 가져오기</h2>
          <p className="text-sm text-muted-foreground">
            들었거나 듣고 있는 강좌에만 들어갈 수 있습니다. 비밀번호는 엔드림스에만 입력하고,
            동국스터디는 과목을 찾는 데 필요한 칸(학기, 학수번호, 분반, 과목명, 교수명)만 받습니다.
            성적은 받지 않습니다.
          </p>
        </div>
      )}
      <ol className="flex flex-col gap-4 text-sm">
        <Step n={1} title="이 버튼을 즐겨찾기 줄로 끌어다 놓으세요 (처음 한 번만)">
          <a
            ref={linkRef}
            onClick={(e) => {
              e.preventDefault()
              alert('누르지 말고 즐겨찾기 줄(Ctrl+Shift+B로 표시)로 끌어다 놓아 주세요.')
            }}
            className="inline-flex cursor-grab items-center gap-2 rounded-md border-2 border-dashed border-primary px-3 py-1.5 font-medium text-primary"
          >
            <Bookmark className="size-4" />
            동국스터디로 보내기
          </a>
        </Step>
        <Step n={2} title="엔드림스를 열고 직접 로그인합니다">
          <Button size="sm" onClick={() => window.open(NDRIMS_URL, 'ndrims')}>
            <ExternalLink />
            엔드림스 열기
          </Button>
        </Step>
        <Step n={3} title="로그인한 창에서 즐겨찾기 '동국스터디로 보내기'를 누릅니다">
          <p className="text-muted-foreground">
            첫 화면에서 눌러도 됩니다. 이번 학기 수강신청 내역과 지난 학기 성적표의 과목 목록을 바로
            가져와 이 창으로 보냅니다.
          </p>
          <details className="text-muted-foreground">
            <summary className="cursor-pointer text-xs">바로 가져오지 못했다고 나오면</summary>
            <ul className="mt-1 list-disc pl-5">
              <li>수강신청 → 수강신청내역확인, 성적 → 전체성적조회 화면을 열면 상자에 모입니다.</li>
              <li>그다음 상자의 [동국스터디로 보내기]를 누릅니다.</li>
            </ul>
          </details>
          {isAdmin && (
            <p className="text-muted-foreground">
              관리자: 수업/강의평가 → 종합강의시간표조회를 열고 상자의 [보내기]를 누르면 개설
              목록이 저장됩니다.
            </p>
          )}
        </Step>
      </ol>
      {save.isPending && <p className="text-sm">가져오는 중…</p>}
      <ErrorText error={save.error} />
      {r && (
        <div className="rounded-lg border bg-muted/40 p-3 text-sm">
          {r.catalog && (
            <p>
              개설 목록 {r.catalog.terms.join(', ')}: 새로 {r.catalog.added}건, 갱신{' '}
              {r.catalog.updated}건 저장
            </p>
          )}
          {r.mine && (
            <p>
              수강 기록 {r.mine.received}건을 받았습니다(새로 {r.mine.added}건). 들어갈 수 있는 강좌{' '}
              {r.mine.courses.length}개, 아직 열리지 않은 수업 {r.mine.waiting.length}개.
            </p>
          )}
        </div>
      )}
    </Card>
  )
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
        {n}
      </span>
      <div className="flex flex-col gap-2">
        <div className="font-medium">{title}</div>
        {children}
      </div>
    </li>
  )
}
