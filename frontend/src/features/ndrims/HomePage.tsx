import { ChevronRight, Lock, RefreshCw, Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { api, unwrap } from '@/api/client'
import { RequestWithFiles } from '@/features/course_requests/RequestWithFiles'
import { Card } from '@/components/ui/card'
import { useAuth } from '@/features/auth/useAuth'
import { ImportPanel } from './ImportPanel'
import { useMyCourses } from './queries'

/** 첫 화면: 수강 기록이 없으면 가져오기 안내, 있으면 내 강좌 */
export function HomePage() {
  const mine = useMyCourses()
  const { user } = useAuth()
  const [reimport, setReimport] = useState(false)

  if (mine.isPending) return <Loading />
  if (!mine.data) return <ErrorText error={mine.error} />
  const d = mine.data

  if (d.record_count === 0)
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold">시작하기</h1>
          <p className="text-sm text-muted-foreground">
            엔드림스 수강 기록을 가져오면 들었거나 듣고 있는 강좌가 자동으로 등록됩니다.
          </p>
        </div>
        <ImportPanel />
        {user?.role === 'admin' && (
          <Link to="/admin/courses" className="text-sm text-primary hover:underline">
            관리자는 모든 강좌에 들어갈 수 있습니다 → 관리 화면
          </Link>
        )}
      </div>
    )

  const current = d.courses.filter((c) => c.status === 'current')
  const taken = d.courses.filter((c) => c.status === 'taken')
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">내 강좌</h1>
          <p className="text-sm text-muted-foreground">
            {d.current_term && `이번 학기 ${d.current_term} · `}수강 기록 {d.record_count}건
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/find" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
            <Search />
            강좌 찾기
          </Link>
          <Button variant="outline" size="sm" onClick={() => setReimport(!reimport)}>
            <RefreshCw />
            수강 기록 다시 가져오기
          </Button>
        </div>
      </div>
      {reimport && <ImportPanel compact />}

      <Section title="수강 중" empty="이번 학기에 열린 강좌가 없습니다.">
        {current.map((c) => (
          <CourseCard key={c.course_id} c={c} />
        ))}
      </Section>
      {taken.length > 0 && (
        <Section title="수강함" empty="">
          {taken.map((c) => (
            <CourseCard key={c.course_id} c={c} />
          ))}
        </Section>
      )}

      {d.waiting.length > 0 && (
        <div className="flex flex-col gap-3">
          <div>
            <h2 className="text-lg font-semibold">아직 열리지 않은 수업</h2>
            <p className="text-sm text-muted-foreground">
              동국스터디에 아직 강좌가 없는 수업입니다. 요청할 때 교안 PDF를 같이 올리면 더 빨리 열립니다(선택).
            </p>
          </div>
          <ul className="flex flex-col divide-y rounded-xl border bg-card">
            {d.waiting.map((w) => (
              <li key={w.enrollment_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <Lock className="size-4 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <div className="font-medium">
                    {w.sbj_nm}
                    {w.professor_name && (
                      <span className="text-muted-foreground"> · {w.professor_name}</span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {w.sbj_no} · {w.term} · {w.status === 'current' ? '수강 중' : '수강함'}
                  </div>
                </div>
                {w.request === 'mine' ? (
                  <Badge variant="secondary">
                    요청함{w.request_count > 1 && ` (${w.request_count}명)`}
                  </Badge>
                ) : (
                  w.professor_name ? (
                    <RequestWithFiles
                      label={`열어 달라고 요청${w.request_count > 0 ? ` (${w.request_count}명 대기)` : ''}`}
                      create={async (note) =>
                        (
                          await unwrap(
                            api.POST('/api/v1/me/enrollments/{enrollment_id}/request', {
                              params: { path: { enrollment_id: w.enrollment_id } },
                              body: { note },
                            }),
                          )
                        ).request_id
                      }
                    />
                  ) : (
                    <Link
                      to={`/requests/new?subject=${encodeURIComponent(w.sbj_nm)}&code=${encodeURIComponent(w.sbj_no)}&semester=${encodeURIComponent(w.term)}`}
                      className={buttonVariants({ size: 'sm', variant: 'outline' })}
                      title="교수 정보가 없어 교수님 이름을 직접 적어 요청합니다"
                    >
                      직접 요청
                    </Link>
                  )
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Section({
  title,
  empty,
  children,
}: {
  title: string
  empty: string
  children: React.ReactNode[]
}) {
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">{children}</div>
      )}
    </div>
  )
}

function CourseCard({
  c,
}: {
  c: { course_id: number; subject_name: string; professor_name: string; terms: string[] }
}) {
  return (
    <Link to={`/courses/${c.course_id}`}>
      <Card className="flex items-center justify-between p-5 transition-colors hover:bg-accent">
        <div>
          <div className="font-semibold">{c.subject_name}</div>
          <div className="text-sm text-muted-foreground">
            {c.professor_name} 교수님 · {c.terms[0]}
          </div>
        </div>
        <ChevronRight className="size-5 text-muted-foreground" />
      </Card>
    </Link>
  )
}
