import { ChevronLeft, ChevronRight, Lock, Search } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { useAuth } from '@/features/auth/useAuth'
import { useCourses, useSubjects } from './queries'

export function SubjectCoursesPage() {
  const subjectId = Number(useParams().subjectId)
  const { user } = useAuth()
  const subject = useSubjects().data?.find((s) => s.id === subjectId)
  const courses = useCourses(subjectId)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/" className="mb-2 inline-flex items-center text-sm text-muted-foreground">
          <ChevronLeft className="size-4" />
          내 강좌
        </Link>
        <h1 className="text-2xl font-bold">{subject?.name ?? '과목'}</h1>
        <p className="text-sm text-muted-foreground">
          수강 기록이 있는 교수님 강좌에만 들어갈 수 있습니다. 다른 교수님 강좌는 잠겨 있습니다.
        </p>
      </div>
      {courses.isPending ? (
        <Loading />
      ) : courses.data?.length === 0 ? (
        <Empty>아직 열린 강좌가 없습니다.</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {courses.data?.map((c) =>
            c.accessible ? (
              <Link key={c.id} to={`/courses/${c.id}`}>
                <Card className="flex items-center justify-between p-5 transition-colors hover:bg-accent">
                  <div className="flex flex-col gap-2">
                    <div className="font-semibold">{c.professor_name} 교수님</div>
                    <div className="flex gap-1.5">
                      <Badge variant="secondary">자료 {c.material_count}</Badge>
                      <Badge variant="secondary">문제 {c.problem_count}</Badge>
                    </div>
                  </div>
                  <ChevronRight className="size-5 text-muted-foreground" />
                </Card>
              </Link>
            ) : (
              <Card key={c.id} className="flex items-center justify-between p-5 opacity-60">
                <div className="font-semibold">{c.professor_name} 교수님</div>
                <Lock className="size-4 text-muted-foreground" />
              </Card>
            ),
          )}
        </div>
      )}
      <ErrorText error={courses.error} />
      <Link to="/find" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
        <Search className="size-4" />
        찾는 강좌가 없으면 강좌 찾기에서 열어 달라고 요청하세요
      </Link>
      <Link
        to={`/requests/new?subject=${encodeURIComponent(subject?.name ?? '')}&code=${encodeURIComponent(subject?.code ?? '')}`}
        className="text-sm text-muted-foreground hover:underline"
      >
        강좌 찾기에도 없으면 직접 요청하기
      </Link>
      {user?.role === 'admin' && (
        <Link to="/admin/courses" className="text-sm text-primary hover:underline">
          관리자: 과목·강좌·교안 직접 추가와 수정은 관리 화면에서
        </Link>
      )}
    </div>
  )
}
