import { ChevronRight, Plus } from 'lucide-react'
import { Link } from 'react-router'
import { Empty, ErrorText, Loading } from '@/components/States'
import { buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useAuth } from '@/features/auth/useAuth'
import { MySubjectButtons } from '@/features/my_subjects/MySubjectButtons'
import { useMySubjects } from '@/features/my_subjects/queries'
import { useSubjects } from './queries'

export function SubjectsPage() {
  const subjects = useSubjects()
  const mine = useMySubjects()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const myIds = new Set(mine.data?.map((m) => m.subject_id))
  const my = subjects.data?.filter((s) => myIds.has(s.id)) ?? []

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">내 과목</h1>
        <p className="text-sm text-muted-foreground">
          수강 중이거나 수강했던 과목만 들어갈 수 있습니다. 아래 전체 과목에서 골라 넣어 주세요.
        </p>
      </div>
      {subjects.isPending || mine.isPending ? (
        <Loading />
      ) : my.length === 0 ? (
        <Empty>아직 내 과목이 없습니다. 아래 전체 과목에서 '내 과목에 추가'를 누르세요.</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {my.map((s) => (
            <Link key={s.id} to={`/subjects/${s.id}`}>
              <Card className="flex items-center justify-between p-5 transition-colors hover:bg-accent">
                <div>
                  <div className="font-semibold">{s.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {s.code && `${s.code} · `}강좌 {s.course_count}개
                  </div>
                </div>
                <ChevronRight className="size-5 text-muted-foreground" />
              </Card>
            </Link>
          ))}
        </div>
      )}
      <ErrorText error={subjects.error ?? mine.error} />

      <div className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">전체 과목</h2>
        {subjects.data?.length === 0 ? (
          <Empty>아직 과목이 없습니다. 아래에서 추가를 요청해 주세요.</Empty>
        ) : (
          <ul className="flex flex-col divide-y rounded-xl border bg-card">
            {subjects.data?.map((s) => (
              <li
                key={s.id}
                className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  {isAdmin || myIds.has(s.id) ? (
                    <Link to={`/subjects/${s.id}`} className="font-medium hover:underline">
                      {s.name}
                    </Link>
                  ) : (
                    <span className="font-medium">{s.name}</span>
                  )}
                  <div className="text-xs text-muted-foreground">
                    {s.code && `${s.code} · `}강좌 {s.course_count}개
                  </div>
                </div>
                <MySubjectButtons subjectId={s.id} added={myIds.has(s.id)} />
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        지금은 직접 고릅니다. 엔드림스 수강 내역 가져오기는 나중에 붙일 예정입니다.
      </p>
      <RequestHint />
      {isAdmin && (
        <Link to="/admin/courses" className="text-sm text-primary hover:underline">
          관리자: 과목·강좌·교안 직접 추가와 수정은 관리 화면에서 (관리자는 모든 과목에 들어갈 수
          있습니다)
        </Link>
      )}
    </div>
  )
}

function RequestHint() {
  return (
    <Card className="flex flex-col items-start gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="text-sm text-muted-foreground">
        찾는 과목이 없나요? 과목·교수님과 교안을 보내 주면 관리자가 확인한 뒤 열어 드립니다.
      </div>
      <Link to="/requests/new" className={buttonVariants({ variant: 'outline' })}>
        <Plus />
        추가 요청
      </Link>
    </Card>
  )
}
