import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, Plus } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/features/auth/useAuth'
import { useSubjects } from './queries'

export function SubjectsPage() {
  const subjects = useSubjects()
  const { user } = useAuth()
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">과목 선택</h1>
        <p className="text-sm text-muted-foreground">과목을 고르면 교수님별 강좌가 나옵니다.</p>
      </div>
      {subjects.isPending ? (
        <Loading />
      ) : subjects.data?.length === 0 ? (
        <Empty>아직 과목이 없습니다. 아래에서 추가를 요청해 주세요.</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {subjects.data?.map((s) => (
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
      <ErrorText error={subjects.error} />
      <RequestHint />
      {user?.role === 'admin' && <AddSubject />}
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

/** 관리자만: 요청 없이 바로 과목 추가 */
function AddSubject() {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const add = useMutation({
    mutationFn: () => unwrap(api.POST('/api/v1/subjects', { body: { name } })),
    onSuccess: () => {
      setName('')
      qc.invalidateQueries({ queryKey: ['subjects'] })
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
          placeholder="관리자: 과목 이름을 입력해 바로 추가"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Button type="submit" variant="outline" disabled={add.isPending}>
          <Plus />
          과목 추가
        </Button>
      </div>
      <ErrorText error={add.error} />
    </form>
  )
}
