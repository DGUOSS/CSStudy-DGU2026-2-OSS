import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Brain, ChevronDown, ChevronRight, Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'
import { api, unwrap } from '@/api/client'
import { ErrorText } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'

/** 관리자: 강좌 객관식의 오개념 상태와 목록(숨기기). 오개념은 문제가 저장될 때 자동으로 붙는다. */
export function MisconceptionAdmin({ courseId }: { courseId: number }) {
  const qc = useQueryClient()
  const [listOpen, setListOpen] = useState(false)
  const key = ['admin', 'courses', courseId, 'misconceptions']
  const status = useQuery({
    queryKey: [...key, 'status'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/admin/courses/{course_id}/misconceptions/status', {
          params: { path: { course_id: courseId } },
        }),
      ),
    refetchInterval: (q) => (q.state.data?.running ? 2000 : false),
  })
  const list = useQuery({
    queryKey: [...key, 'list'],
    enabled: listOpen,
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/admin/courses/{course_id}/misconceptions', {
          params: { path: { course_id: courseId } },
        }),
      ),
  })
  const setStatus = useMutation({
    mutationFn: ({ id, s }: { id: number; s: 'auto' | 'hidden' }) =>
      unwrap(
        api.PATCH('/api/v1/admin/misconceptions/{misconception_id}', {
          params: { path: { misconception_id: id } },
          body: { status: s },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...key, 'list'] }),
  })

  const s = status.data
  return (
    <div className="flex flex-col gap-2 rounded-lg border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Brain className="size-4" />
        <b>오개념</b>
        {s && (
          <span className="text-muted-foreground">
            객관식 {s.problems}문제 중 {s.covered}문제에 붙음 (오개념 {s.misconceptions}개)
          </span>
        )}
        <div className="ml-auto flex gap-1">
          <Button size="sm" variant="ghost" onClick={() => setListOpen(!listOpen)}>
            {listOpen ? <ChevronDown /> : <ChevronRight />}
            목록
          </Button>
        </div>
      </div>
      {s?.running && (
        <div className="flex items-center gap-2">
          <Progress value={(s.done / Math.max(1, s.total)) * 100} className="h-2" />
          <span className="shrink-0 tabular-nums text-muted-foreground">
            {s.done}/{s.total}
            {s.failed > 0 && ` (실패 ${s.failed})`}
          </span>
        </div>
      )}
      {s?.error && <p className="text-destructive">{s.error}</p>}
      {!s?.running && s && s.failed > 0 && (
        <p className="text-[#8a6212]">
          지난번 {s.failed}문제는 만들지 못했습니다. 다시 누르면 남은 것만 만듭니다.
        </p>
      )}
      <ErrorText error={status.error ?? setStatus.error} />
      {listOpen && (
        <div className="flex max-h-[28rem] flex-col gap-2 overflow-y-auto">
          {list.data?.length === 0 && <p className="text-muted-foreground">아직 없습니다.</p>}
          {list.data?.map((m) => (
            <div
              key={m.id}
              className={`rounded-md border p-2 ${m.status === 'hidden' ? 'opacity-50' : ''}`}
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted-foreground">문제 #{m.problem_id}</span>
                <b>{m.label}</b>
                {m.evidence_found ? (
                  <Badge variant="outline" className="border-success text-success">
                    근거 확인
                  </Badge>
                ) : (
                  <Badge variant="outline" title="근거 문장이 교안 쪽에 없어 학생에게 안 보입니다">
                    근거 없음 · 안 보임
                  </Badge>
                )}
                {m.status === 'hidden' && <Badge variant="secondary">숨김</Badge>}
                <Button
                  size="sm"
                  variant="ghost"
                  className="ml-auto h-7"
                  onClick={() =>
                    setStatus.mutate({ id: m.id, s: m.status === 'hidden' ? 'auto' : 'hidden' })
                  }
                >
                  {m.status === 'hidden' ? <Eye /> : <EyeOff />}
                  {m.status === 'hidden' ? '다시 보이기' : '숨기기'}
                </Button>
              </div>
              <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                {m.question} — 오답 「{m.choice}」
              </p>
              <p className="mt-1">{m.hypothesis}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
