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
import { cn } from '@/lib/utils'
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
  const [mcq, setMcq] = useState(15)
  const [essay, setEssay] = useState(0)
  const [limit, setLimit] = useState(30)
  const list = chapters.data ?? []
  const inRange = list.filter((c) => picked.includes(c.id))
  const haveMcq = inRange.reduce((n, c) => n + c.problem_count, 0)
  const haveEssay = inRange.reduce((n, c) => n + c.essay_count, 0)
  const usable = list.filter((c) => c.problem_count + c.essay_count > 0)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(
      {
        title: title.trim() || '모의고사',
        chapter_ids: picked,
        mcq_count: mcq,
        essay_count: essay,
        time_limit_min: limit,
      },
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
      <form onSubmit={submit} className="flex flex-col gap-5">
        <div className="grid gap-2">
          <div className="flex items-center justify-between">
            <Label>범위 (챕터)</Label>
            <button
              type="button"
              className="cursor-pointer text-xs text-primary hover:underline"
              onClick={() =>
                setPicked(picked.length === usable.length ? [] : usable.map((c) => c.id))
              }
            >
              {picked.length === usable.length && usable.length > 0 ? '모두 해제' : '모두 고르기'}
            </button>
          </div>
          {chapters.isPending ? (
            <Loading />
          ) : (
            <div className="flex flex-wrap gap-2">
              {list.map((c) => {
                const on = picked.includes(c.id)
                return (
                  <button
                    type="button"
                    key={c.id}
                    disabled={c.problem_count + c.essay_count === 0}
                    onClick={() =>
                      setPicked(on ? picked.filter((x) => x !== c.id) : [...picked, c.id])
                    }
                    className={cn(
                      'cursor-pointer rounded-full border px-3 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-40',
                      on ? 'border-primary bg-primary text-primary-foreground' : 'bg-card',
                    )}
                  >
                    {c.title}
                    <span
                      className={cn('ml-1 text-xs', on ? 'opacity-80' : 'text-muted-foreground')}
                    >
                      객{c.problem_count}
                      {c.essay_count > 0 && ` · 서${c.essay_count}`}
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <CountField
            id="pmcq"
            label="객관식"
            value={mcq}
            onChange={setMcq}
            have={picked.length ? haveMcq : null}
          />
          <CountField
            id="pessay"
            label="서술형"
            value={essay}
            onChange={setEssay}
            have={picked.length ? haveEssay : null}
          />
        </div>
        <p className="-mt-3 text-xs text-muted-foreground">
          고른 챕터를 돌아가며 골고루 뽑습니다. 족보 형식에 맞춘 유형 비율은 문제 생성이 연결되면
          자동으로 채워집니다.
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
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
            <Label htmlFor="plimit">제한 시간(분)</Label>
            <div className="flex items-center gap-2">
              <Input
                id="plimit"
                type="number"
                min={5}
                max={300}
                className="w-24"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
              />
              {[20, 30, 50, 75].map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setLimit(m)}
                  className={cn(
                    'cursor-pointer rounded-md border px-2 py-1 text-xs',
                    limit === m && 'border-primary text-primary',
                  )}
                >
                  {m}분
                </button>
              ))}
            </div>
          </div>
        </div>

        <ErrorText error={create.error} />
        <div className="flex items-center gap-2">
          <Button type="submit" disabled={!picked.length || mcq + essay === 0 || create.isPending}>
            {create.isPending ? '만드는 중…' : '만들기'}
          </Button>
          <Button type="button" variant="ghost" onClick={onDone}>
            취소
          </Button>
          {picked.length > 0 && (
            <span className="ml-auto text-xs text-muted-foreground">
              {Math.min(mcq, haveMcq) + Math.min(essay, haveEssay)}문항으로 만들어집니다
            </span>
          )}
        </div>
      </form>
    </Card>
  )
}

function CountField({
  id,
  label,
  value,
  onChange,
  have,
}: {
  id: string
  label: string
  value: number
  onChange: (n: number) => void
  have: number | null
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>
        {label} 문항 수
        {have != null && (
          <span className="ml-1 font-normal text-muted-foreground">(고른 범위에 {have}개)</span>
        )}
      </Label>
      <div className="flex items-center gap-1">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => onChange(Math.max(0, value - 1))}
        >
          −
        </Button>
        <Input
          id={id}
          type="number"
          min={0}
          className="w-20 text-center"
          value={value}
          onChange={(e) => onChange(Math.max(0, Number(e.target.value)))}
        />
        <Button type="button" size="sm" variant="outline" onClick={() => onChange(value + 1)}>
          +
        </Button>
        {have != null && value > have && (
          <span className="ml-2 text-xs text-amber-700">있는 {have}개만 들어갑니다</span>
        )}
      </div>
    </div>
  )
}
