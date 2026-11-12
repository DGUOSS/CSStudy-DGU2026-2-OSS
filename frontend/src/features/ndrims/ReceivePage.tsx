import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { ErrorText } from '@/components/States'
import { buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useAuth } from '@/features/auth/useAuth'
import { useImportNdrims } from './queries'
import { takeStashed } from './receive'

export function ReceivePage() {
  const { user } = useAuth()
  const save = useImportNdrims(user?.role === 'admin')
  const [payload] = useState(takeStashed)
  const sent = useRef(false)

  useEffect(() => {
    if (payload && !sent.current) {
      sent.current = true
      save.mutate(payload)
    }
  }, [payload, save])

  const r = save.data
  return (
    <Card className="mx-auto flex max-w-xl flex-col gap-4 p-6">
      <h1 className="text-xl font-bold">엔드림스 기록 받기</h1>
      {!payload && (
        <p className="text-sm text-muted-foreground">
          받은 기록이 없습니다. 엔드림스 창의 [동국스터디로 보내기]를 다시 눌러 주세요.
        </p>
      )}
      {save.isPending && <p className="text-sm">저장하는 중…</p>}
      <ErrorText error={save.error} />
      {r && (
        <div className="flex flex-col gap-1 text-sm">
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
      <Link to="/" className={buttonVariants({ className: 'self-start' })}>
        내 강좌로 가기
      </Link>
    </Card>
  )
}
