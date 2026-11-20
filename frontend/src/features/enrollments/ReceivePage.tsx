import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { ErrorText } from '@/components/States'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useAuth } from '@/features/auth/useAuth'
import { useImportNdrims } from './queries'
import { SyllabusResult } from './SyllabusResult'
import { MESSAGE_TYPE, NDRIMS_ORIGINS, type NdrimsPayload } from './bookmarklet'
import { donePull, PULL_TYPE, wantsPull } from './receive'

/**
 * 새 탭으로 받은 엔드림스 기록(/ndrims#...)을 보여 주고, 사용자가 확인한 뒤에만 저장한다.
 * 이 주소는 아무 사이트나 열 수 있으므로 자동 저장하지 않는다(가짜 기록·가짜 개설 목록 주입 방지).
 */
export function ReceivePage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const save = useImportNdrims(isAdmin)
  const [payload, setPayload] = useState<NdrimsPayload | null>(null)
  const [waiting, setWaiting] = useState(wantsPull)

  // 이 탭을 연 엔드림스 창에 기록을 달라고 한다(받을 때까지 1초마다, 15번)
  useEffect(() => {
    if (!waiting) return
    const onMessage = (e: MessageEvent) => {
      if (!NDRIMS_ORIGINS.includes(e.origin)) return
      const d = e.data as NdrimsPayload
      if (d?.type !== MESSAGE_TYPE) return
      setPayload(d)
      setWaiting(false)
      donePull()
    }
    window.addEventListener('message', onMessage)
    let n = 0
    const ask = () => {
      if (n++ >= 15) {
        setWaiting(false)
        donePull()
        return
      }
      for (const o of NDRIMS_ORIGINS) window.opener?.postMessage({ type: PULL_TYPE }, o)
    }
    ask()
    const t = setInterval(ask, 1000)
    return () => {
      clearInterval(t)
      window.removeEventListener('message', onMessage)
    }
  }, [waiting])

  const r = save.data
  return (
    <Card className="mx-auto flex max-w-xl flex-col gap-4 p-6">
      <h1 className="text-xl font-bold">엔드림스 기록 받기</h1>
      {waiting && <p className="text-sm">엔드림스 창에서 받는 중…</p>}
      {!waiting && !payload && !r && (
        <p className="text-sm text-muted-foreground">
          받은 기록이 없습니다. 엔드림스 창의 [동국스터디로 보내기]를 다시 눌러 주세요. 엔드림스
          창을 닫았다면 다시 열어야 합니다.
        </p>
      )}
      {payload && !r && (
        <>
          <p className="text-sm text-muted-foreground">
            엔드림스 창에서 [동국스터디로 보내기]를 직접 누른 경우에만 가져오세요. 아래 내용이 내
            수강 내역과 맞는지 확인해 주세요.
          </p>
          {payload.records.length > 0 && (
            <ul className="max-h-64 overflow-auto rounded-lg border text-sm">
              {payload.records.map((x) => (
                <li
                  key={[x.year, x.sem_cd, x.sbj_no, x.dvcls].join('|')}
                  className="flex justify-between gap-2 border-b px-3 py-1.5 last:border-0"
                >
                  <span className="truncate">
                    {x.sbj_nm}
                    {x.emp_nm && <span className="text-muted-foreground"> · {x.emp_nm}</span>}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {x.year} {x.sbj_no}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {isAdmin && payload.catalog.length > 0 && (
            <p className="text-sm">관리자: 개설 목록 {payload.catalog.length}건을 저장합니다.</p>
          )}
          {isAdmin && (payload.syllabi?.length ?? 0) > 0 && (
            <p className="text-sm">관리자: 강의계획서 {payload.syllabi?.length}건으로 팀플 여부를 판정합니다.</p>
          )}
          <div className="flex gap-2">
            <Button disabled={save.isPending} onClick={() => save.mutate(payload)}>
              {save.isPending
                ? '저장하는 중…'
                : [
                    payload.records.length > 0 && `수강 기록 ${payload.records.length}건`,
                    isAdmin &&
                      payload.catalog.length > 0 &&
                      `개설 목록 ${payload.catalog.length}건`,
                    isAdmin && (payload.syllabi?.length ?? 0) > 0 && `계획서 ${payload.syllabi?.length}건`,
                  ]
                    .filter(Boolean)
                    .join(' + ') + ' 가져오기'}
            </Button>
            <Button variant="ghost" disabled={save.isPending} onClick={() => setPayload(null)}>
              가져오지 않기
            </Button>
          </div>
        </>
      )}
      <ErrorText error={save.error} />
      {r && (
        <div className="flex flex-col gap-1 text-sm">
          {r.catalogError && (
            <p className="text-destructive">
              개설 목록·계획서는 저장하지 못했습니다: {r.catalogError.message}
            </p>
          )}
          {r.catalog && (
            <p>
              개설 목록 {r.catalog.terms.join(', ')}: 새로 {r.catalog.added}건, 갱신{' '}
              {r.catalog.updated}건 저장
            </p>
          )}
          <SyllabusResult r={r.syllabi} />
          {r.mine && (
            <p>
              수강 기록 {r.mine.received}건을 받았습니다(새로 {r.mine.added}건). 들어갈 수 있는 강좌{' '}
              {r.mine.courses.length}개, 아직 열리지 않은 수업 {r.mine.waiting.length}개.
            </p>
          )}
        </div>
      )}
      <Link to="/" className={buttonVariants({ variant: 'outline', className: 'self-start' })}>
        내 강좌로 가기
      </Link>
    </Card>
  )
}
