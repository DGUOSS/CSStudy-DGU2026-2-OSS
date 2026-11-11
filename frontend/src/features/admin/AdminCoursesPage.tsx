import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, FileText, Pencil, Plus, Trash2 } from 'lucide-react'
import { type FormEvent, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api, type Schemas, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCourses, useSubjects } from '@/features/courses/queries'
import { UploadForm } from '@/features/materials/MaterialsTab'
import { resultText } from '@/features/materials/resultText'
import { AdminNav } from './AdminNav'

const KIND_LABEL: Record<string, string> = { lecture: '교안', exam: '기출·족보', note: '시험 정보' }
type Kind = 'lecture' | 'exam' | 'note'

/** 관리자: 과목·강좌를 직접 만들고(교안 여러 개 함께), 기존 과목·강좌·교안을 고치고 지운다. */
export function AdminCoursesPage() {
  const subjects = useSubjects()
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">관리</h1>
        <p className="text-sm text-muted-foreground">
          교안은 쪽 내용으로 비교해서 같은 내용은 건너뛰고, 수정본은 새 판으로 바꿉니다.
        </p>
      </div>
      <AdminNav />
      <CreateCourseCard subjectNames={subjects.data?.map((s) => s.name) ?? []} />
      <h2 className="text-lg font-semibold">등록된 과목</h2>
      {subjects.isPending ? (
        <Loading />
      ) : subjects.data?.length === 0 ? (
        <Empty>과목이 없습니다.</Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {subjects.data?.map((s) => (
            <SubjectRow key={s.id} subject={s} />
          ))}
        </div>
      )}
      <ErrorText error={subjects.error} />
    </div>
  )
}

function CreateCourseCard({ subjectNames }: { subjectNames: string[] }) {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [subjectName, setSubjectName] = useState('')
  const [subjectCode, setSubjectCode] = useState('')
  const [professorName, setProfessorName] = useState('')
  const [kind, setKind] = useState<Kind>('lecture')

  const create = useMutation({
    mutationFn: () => {
      const form = new FormData()
      form.append('subject_name', subjectName)
      form.append('professor_name', professorName)
      form.append('kind', kind)
      if (subjectCode) form.append('subject_code', subjectCode)
      for (const f of Array.from(fileRef.current?.files ?? [])) form.append('files', f)
      return unwrap(
        api.POST('/api/v1/admin/courses', {
          // multipart는 openapi-fetch가 타입으로 표현하지 못해서 FormData를 그대로 보낸다
          body: form as never,
          bodySerializer: (b) => b as unknown as FormData,
        }),
      )
    },
    onSuccess: () => {
      if (fileRef.current) fileRef.current.value = ''
      qc.invalidateQueries({ queryKey: ['subjects'] })
      qc.invalidateQueries({ queryKey: ['courses'] })
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">과목·강좌 추가 (교안 함께)</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="grid gap-2">
              <Label htmlFor="a-subject">과목명</Label>
              <Input
                id="a-subject"
                list="a-subjects"
                required
                placeholder="기존 과목을 고르거나 새로 입력"
                value={subjectName}
                onChange={(e) => setSubjectName(e.target.value)}
              />
              <datalist id="a-subjects">
                {subjectNames.map((n) => (
                  <option key={n} value={n} />
                ))}
              </datalist>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="a-code">학수번호 (선택)</Label>
              <Input id="a-code" value={subjectCode} onChange={(e) => setSubjectCode(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="a-prof">교수님 이름</Label>
              <Input
                id="a-prof"
                required
                value={professorName}
                onChange={(e) => setProfessorName(e.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-2">
            <Label>자료 (선택, 여러 개 가능)</Label>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
                <Button
                  key={k}
                  type="button"
                  size="sm"
                  variant={kind === k ? 'default' : 'outline'}
                  onClick={() => setKind(k)}
                >
                  {KIND_LABEL[k]}
                </Button>
              ))}
            </div>
            <Input ref={fileRef} type="file" accept="application/pdf,.pdf" multiple aria-label="PDF" />
            <p className="text-xs text-muted-foreground">
              이미 있는 강좌를 적으면 강좌는 그대로 두고 자료만 붙입니다. 파일 이름이 자료 제목이 됩니다.
            </p>
          </div>
          <ErrorText error={create.error} />
          <div>
            <Button type="submit" disabled={create.isPending}>
              <Plus />
              {create.isPending ? '처리 중…' : '추가'}
            </Button>
          </div>
          {create.data && (
            <div className="rounded-lg border bg-muted/40 p-3 text-sm">
              <div className="font-medium">
                {create.data.course.subject_name} · {create.data.course.professor_name} 교수님{' '}
                {create.data.created ? '강좌를 만들었습니다.' : '(이미 있던 강좌)'}{' '}
                <Link className="text-primary underline" to={`/courses/${create.data.course.id}`}>
                  강좌 보기
                </Link>
              </div>
              <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                {create.data.uploads.map((u) => (
                  <li key={`${u.id}-${u.filename}`}>
                    {u.filename}: {resultText(u)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  )
}

function SubjectRow({ subject }: { subject: Schemas['SubjectOut'] }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(subject.name)
  const [code, setCode] = useState(subject.code ?? '')
  const refresh = () => qc.invalidateQueries({ queryKey: ['subjects'] })
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH('/api/v1/admin/subjects/{subject_id}', {
          params: { path: { subject_id: subject.id } },
          body: { name, code },
        }),
      ),
    onSuccess: () => {
      setEditing(false)
      refresh()
    },
  })
  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE('/api/v1/admin/subjects/{subject_id}', {
          params: { path: { subject_id: subject.id } },
        }),
      ),
    onSuccess: refresh,
  })

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => setOpen(!open)} aria-label="펼치기">
          {open ? <ChevronDown /> : <ChevronRight />}
        </Button>
        {editing ? (
          <>
            <Input className="max-w-56" value={name} onChange={(e) => setName(e.target.value)} />
            <Input
              className="max-w-32"
              placeholder="학수번호"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
            <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
              저장
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              취소
            </Button>
          </>
        ) : (
          <>
            <span className="font-semibold">{subject.name}</span>
            {subject.code && <Badge variant="outline">{subject.code}</Badge>}
            <span className="text-sm text-muted-foreground">강좌 {subject.course_count}개</span>
            <div className="ml-auto flex gap-1">
              <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
                <Pencil />
                이름 수정
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => confirm(`'${subject.name}' 과목을 지울까요?`) && remove.mutate()}
              >
                <Trash2 />
                삭제
              </Button>
            </div>
          </>
        )}
      </div>
      <ErrorText error={save.error ?? remove.error} />
      {open && <CourseList subjectId={subject.id} />}
    </Card>
  )
}

function CourseList({ subjectId }: { subjectId: number }) {
  const courses = useCourses(subjectId)
  if (courses.isPending) return <Loading />
  if (!courses.data?.length) return <p className="mt-3 pl-10 text-sm text-muted-foreground">강좌가 없습니다.</p>
  return (
    <div className="mt-3 flex flex-col gap-2 pl-10">
      {courses.data.map((c) => (
        <CourseRow key={c.id} course={c} />
      ))}
    </div>
  )
}

function CourseRow({ course }: { course: Schemas['CourseOut'] }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [prof, setProf] = useState(course.professor_name)
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['subjects'] })
    qc.invalidateQueries({ queryKey: ['courses', course.id] })
  }
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH('/api/v1/admin/courses/{course_id}', {
          params: { path: { course_id: course.id } },
          body: { professor_name: prof },
        }),
      ),
    onSuccess: () => {
      setEditing(false)
      refresh()
    },
  })
  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE('/api/v1/admin/courses/{course_id}', {
          params: { path: { course_id: course.id } },
        }),
      ),
    onSuccess: refresh,
  })

  return (
    <div className="rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => setOpen(!open)} aria-label="자료 펼치기">
          {open ? <ChevronDown /> : <ChevronRight />}
        </Button>
        {editing ? (
          <>
            <Input className="max-w-48" value={prof} onChange={(e) => setProf(e.target.value)} />
            <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
              저장
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              취소
            </Button>
          </>
        ) : (
          <>
            <Link to={`/courses/${course.id}`} className="font-medium hover:underline">
              {course.professor_name} 교수님
            </Link>
            <Badge variant="secondary">자료 {course.material_count}</Badge>
            <Badge variant="secondary">문제 {course.problem_count}</Badge>
            <div className="ml-auto flex gap-1">
              <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
                <Pencil />
                교수명 수정
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  confirm(`${course.professor_name} 교수님 강좌와 자료를 지울까요?`) && remove.mutate()
                }
              >
                <Trash2 />
                삭제
              </Button>
            </div>
          </>
        )}
      </div>
      <ErrorText error={save.error ?? remove.error} />
      {open && (
        <div className="mt-3 flex flex-col gap-3">
          <MaterialsAdmin courseId={course.id} />
          <UploadForm courseId={course.id} />
        </div>
      )}
    </div>
  )
}

function MaterialsAdmin({ courseId }: { courseId: number }) {
  const materials = useQuery({
    queryKey: ['courses', courseId, 'materials', 'all'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/courses/{course_id}/materials', {
          params: { path: { course_id: courseId }, query: { all_versions: true } },
        }),
      ),
  })
  if (materials.isPending) return <Loading />
  if (!materials.data?.length) return <p className="text-sm text-muted-foreground">자료가 없습니다.</p>
  return (
    <ul className="flex flex-col divide-y rounded-lg border bg-card">
      {materials.data.map((m) => (
        <MaterialRow key={m.id} m={m} courseId={courseId} />
      ))}
    </ul>
  )
}

function MaterialRow({ m, courseId }: { m: Schemas['MaterialOut']; courseId: number }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(m.title)
  const [kind, setKind] = useState<Kind>(m.kind as Kind)
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['courses', courseId] })
    qc.invalidateQueries({ queryKey: ['subjects'] })
  }
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH('/api/v1/admin/materials/{material_id}', {
          params: { path: { material_id: m.id } },
          body: { title, kind },
        }),
      ),
    onSuccess: () => {
      setEditing(false)
      refresh()
    },
  })
  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE('/api/v1/admin/materials/{material_id}', {
          params: { path: { material_id: m.id } },
        }),
      ),
    onSuccess: refresh,
  })
  const old = m.replaced_by != null

  return (
    <li className={old ? 'px-3 py-2 opacity-60' : 'px-3 py-2'}>
      <div className="flex flex-wrap items-center gap-2">
        <FileText className="size-4 shrink-0 text-muted-foreground" />
        {editing ? (
          <>
            <Input className="max-w-64" value={title} onChange={(e) => setTitle(e.target.value)} />
            {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
              <Button
                key={k}
                type="button"
                size="sm"
                variant={kind === k ? 'default' : 'outline'}
                onClick={() => setKind(k)}
              >
                {KIND_LABEL[k]}
              </Button>
            ))}
            <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
              저장
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              취소
            </Button>
          </>
        ) : (
          <>
            <span className="text-sm font-medium">{m.title}</span>
            <Badge variant="outline">{KIND_LABEL[m.kind] ?? m.kind}</Badge>
            <Badge variant={old ? 'outline' : 'secondary'}>
              {m.version ?? 1}판{old ? ' (옛 판)' : ' 최신'}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {m.filename} · {m.page_count}쪽
            </span>
            <div className="ml-auto flex gap-1">
              <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
                <Pencil />
                수정
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  confirm(
                    old
                      ? `옛 판 '${m.title}'을 지울까요?`
                      : `'${m.title}'을 지울까요? 이전 판이 있으면 그 판이 다시 최신판이 됩니다.`,
                  ) && remove.mutate()
                }
              >
                <Trash2 />
                삭제
              </Button>
            </div>
          </>
        )}
      </div>
      <ErrorText error={save.error ?? remove.error} />
    </li>
  )
}
