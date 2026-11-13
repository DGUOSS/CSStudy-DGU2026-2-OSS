import { useQuery } from '@tanstack/react-query'
import { ChevronRight, FileText, Plus } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCreatePaper, usePapers } from './queries'

/** 강좌의 '시험' 탭: 종이 시험지 목록과 만들기 */
export function PapersTab({ courseId }: { courseId: number }) {
  const papers = usePapers(courseId)
  const [creating, setCreating] = useState(false)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          시험지를 인쇄해 시간을 재며 풀고, 답안지를 사진으로 찍어 채점합니다. 같은 시험지를 본
          사람끼리 등수가 나옵니다.
        </p>
        <Button size="sm" onClick={() => setCreating(!creating)}>
          <Plus />
          시험지 만들기
        </Button>
      </div>
      {creating && <CreatePaper courseId={courseId} onDone={() => setCreating(false)} />}
      {papers.isPending ? (
        <Loading />
      ) : !papers.data?.length ? (
        <Empty>아직 시험지가 없습니다. 챕터를 골라 첫 시험지를 만들어 보세요.</Empty>
      ) : (
        <div className="flex flex-col gap-2">
          {papers.data.map((p) => (
            <Link key={p.id} to={`/papers/${p.id}`}>
              <Card className="flex items-center gap-3 p-4 transition-colors hover:bg-accent">
                <FileText className="size-5 shrink-0 text-primary" />
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{p.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.n_questions}문항{p.n_essay > 0 && `(서술형 ${p.n_essay})`} ·{' '}
                    {p.time_limit_min}분 · 응시 {p.takers}명{p.created_by_me && ' · 내가 만듦'}
                  </div>
                </div>
                {p.my_open_take_id && <Badge>푸는 중</Badge>}
                {p.my_best != null && (
                  <Badge variant="secondary">
                    내 점수 {p.my_best}/{p.total_points}
                  </Badge>
                )}
                <ChevronRight className="size-5 text-muted-foreground" />
              </Card>
            </Link>
          ))}
        </div>
      )}
      <ErrorText error={papers.error} />
    </div>
  )
}

function CreatePaper({ courseId, onDone }: { courseId: number; onDone: () => void }) {
  const navigate = useNavigate()
  const chapters = useQuery({
    queryKey: ['courses', courseId, 'chapters'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/courses/{course_id}/chapters', {
          params: { path: { course_id: courseId } },
        }),
      ),
  })
  const create = useCreatePaper(courseId)
  const [picked, setPicked] = useState<number[]>([])
  const [title, setTitle] = useState('')
  const [count, setCount] = useState(20)
  const [limit, setLimit] = useState(30)
  const available = (chapters.data ?? [])
    .filter((c) => picked.includes(c.id))
    .reduce((n, c) => n + c.problem_count, 0)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(
      { title: title.trim() || '모의고사', chapter_ids: picked, count, time_limit_min: limit },
      {
        onSuccess: (p) => {
          onDone()
          navigate(`/papers/${p.id}`)
        },
      },
    )
  }

  return (
    <Card className="p-4">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid gap-2">
          <Label>범위 (챕터)</Label>
          {chapters.isPending ? (
            <Loading />
          ) : (
            <div className="flex flex-wrap gap-2">
              {chapters.data?.map((c) => {
                const on = picked.includes(c.id)
                return (
                  <button
                    type="button"
                    key={c.id}
                    disabled={c.problem_count === 0}
                    onClick={() =>
                      setPicked(on ? picked.filter((x) => x !== c.id) : [...picked, c.id])
                    }
                    className={`cursor-pointer rounded-full border px-3 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-40 ${
                      on ? 'border-primary bg-primary text-primary-foreground' : 'bg-card'
                    }`}
                  >
                    {c.order}. {c.title} ({c.problem_count})
                  </button>
                )
              })}
            </div>
          )}
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="grid gap-2">
            <Label htmlFor="ptitle">제목</Label>
            <Input
              id="ptitle"
              placeholder="모의고사"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="pcount">문항 수</Label>
            <Input
              id="pcount"
              type="number"
              min={1}
              max={100}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="plimit">제한 시간(분)</Label>
            <Input
              id="plimit"
              type="number"
              min={5}
              max={300}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
          </div>
        </div>
        {picked.length > 0 && available < count && (
          <p className="text-xs text-muted-foreground">
            고른 범위에 문제가 {available}개라 {available}문항으로 만듭니다.
          </p>
        )}
        <ErrorText error={create.error} />
        <div className="flex gap-2">
          <Button type="submit" disabled={!picked.length || create.isPending}>
            {create.isPending ? '만드는 중…' : '만들기'}
          </Button>
          <Button type="button" variant="ghost" onClick={onDone}>
            취소
          </Button>
        </div>
      </form>
    </Card>
  )
}
