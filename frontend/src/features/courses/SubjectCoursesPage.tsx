import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
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
          과목 목록
        </Link>
        <h1 className="text-2xl font-bold">{subject?.name ?? '과목'}</h1>
        <p className="text-sm text-muted-foreground">교수님을 고르세요.</p>
      </div>
      {courses.isPending ? (
        <Loading />
      ) : courses.data?.length === 0 ? (
        <Empty>아직 등록된 강좌가 없습니다. 아래에서 추가를 요청해 주세요.</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {courses.data?.map((c) => (
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
          ))}
        </div>
      )}
      <ErrorText error={courses.error} />
      <Card className="flex flex-col items-start gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-muted-foreground">
          찾는 교수님 강좌가 없나요? 교안과 함께 요청하면 관리자가 확인한 뒤 열어 드립니다.
        </div>
        <Link
          to={`/requests/new?subject=${encodeURIComponent(subject?.name ?? '')}`}
          className={buttonVariants({ variant: 'outline' })}
        >
          <Plus />
          강좌 추가 요청
        </Link>
      </Card>
      {user?.role === 'admin' && <AddCourse subjectId={subjectId} />}
    </div>
  )
}

/** 관리자만: 요청 없이 바로 강좌 추가 */
function AddCourse({ subjectId }: { subjectId: number }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const add = useMutation({
    mutationFn: () =>
      unwrap(api.POST('/api/v1/courses', { body: { subject_id: subjectId, professor_name: name } })),
    onSuccess: (course) => {
      qc.invalidateQueries({ queryKey: ['subjects'] })
      navigate(`/courses/${course.id}`)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    add.mutate()
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <div className="flex gap-2">
        <Input
          placeholder="관리자: 교수님 이름을 입력해 바로 추가"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Button type="submit" variant="outline" disabled={add.isPending}>
          <Plus />
          강좌 추가
        </Button>
      </div>
      <ErrorText error={add.error} />
    </form>
  )
}
