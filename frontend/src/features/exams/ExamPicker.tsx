import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ThumbsDown, ThumbsUp } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { type Schemas, api, unwrap } from '@/api/client'
import { ErrorText, Loading } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type Exam = Schemas['ExamOut']

/** 문제 풀기 전에 참고할 족보를 고른다. 족보마다 좋아요/싫어요를 누를 수 있다. */
export function ExamPicker({ courseId }: { courseId: number }) {
  const qc = useQueryClient()
  const key = ['courses', courseId, 'exams']
  const exams = useQuery({
    queryKey: key,
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/courses/{course_id}/exams', {
          params: { path: { course_id: courseId } },
        }),
      ),
  })
  // 저장 전에 바꾼 선택. null이면 서버에 저장된 선택을 그대로 보여 준다.
  const [draft, setDraft] = useState<Set<number> | null>(null)

  const save = useMutation({
    mutationFn: (ids: number[]) =>
      unwrap(
        api.PUT('/api/v1/courses/{course_id}/exam-selection', {
          params: { path: { course_id: courseId } },
          body: { material_ids: ids },
        }),
      ),
    onSuccess: (data) => {
      qc.setQueryData(key, data)
      setDraft(null)
    },
  })

  const vote = useMutation({
    mutationFn: ({ id, value }: { id: number; value: 1 | -1 | 0 }) =>
      unwrap(
        api.PUT('/api/v1/materials/{material_id}/vote', {
          params: { path: { material_id: id } },
          body: { value },
        }),
      ),
    onSuccess: (v) =>
      qc.setQueryData<Exam[]>(key, (old) =>
        old
          ?.map((e) =>
            e.id === v.material_id
              ? { ...e, likes: v.likes, dislikes: v.dislikes, my_vote: v.my_vote }
              : e,
          )
          .sort((a, b) => b.likes - b.dislikes - (a.likes - a.dislikes)),
      ),
  })

  if (exams.isPending) return <Loading />
  if (!exams.data) return <ErrorText error={exams.error} />

  const saved = new Set(exams.data.filter((e) => e.selected).map((e) => e.id))
  const picked = draft ?? saved
  const dirty = saved.size !== picked.size || [...picked].some((id) => !saved.has(id))
  const toggle = (id: number) =>
    setDraft(() => {
      const next = new Set(picked)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">참고할 족보 고르기</CardTitle>
        <p className="text-sm text-muted-foreground">
          고른 족보는 AI 문제 생성 때 출제 스타일 참고로 쓰입니다(문제 생성은 준비 중). 좋아요가
          많은 족보가 위에 옵니다.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {exams.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            아직 올라온 족보가 없습니다. 자료 탭의 '족보'에서 올려 주세요.
          </p>
        ) : (
          <ul className="flex flex-col divide-y rounded-lg border">
            {exams.data.map((e) => (
              <li key={e.id} className="flex items-center gap-3 px-3 py-2">
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={picked.has(e.id)}
                  aria-label={`${e.title} 선택`}
                  onClick={() => toggle(e.id)}
                  className={cn(
                    'flex size-5 shrink-0 cursor-pointer items-center justify-center rounded border',
                    picked.has(e.id) && 'border-primary bg-primary text-primary-foreground',
                  )}
                >
                  {picked.has(e.id) && <Check className="size-3.5" />}
                </button>
                <button
                  type="button"
                  onClick={() => toggle(e.id)}
                  className="min-w-0 flex-1 cursor-pointer text-left"
                >
                  <div className="truncate text-sm font-medium">{e.title}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {e.filename} · {e.page_count}쪽{e.uploader_name && ` · ${e.uploader_name}`}
                  </div>
                </button>
                <VoteButton
                  active={e.my_vote === 1}
                  count={e.likes}
                  label="좋아요"
                  disabled={vote.isPending}
                  onClick={() => vote.mutate({ id: e.id, value: e.my_vote === 1 ? 0 : 1 })}
                >
                  <ThumbsUp />
                </VoteButton>
                <VoteButton
                  active={e.my_vote === -1}
                  count={e.dislikes}
                  label="싫어요"
                  disabled={vote.isPending}
                  onClick={() => vote.mutate({ id: e.id, value: e.my_vote === -1 ? 0 : -1 })}
                >
                  <ThumbsDown />
                </VoteButton>
              </li>
            ))}
          </ul>
        )}
        <ErrorText error={save.error ?? vote.error} />
        {exams.data.length > 0 && (
          <div className="flex items-center gap-3">
            <Button
              type="button"
              size="sm"
              disabled={!dirty || save.isPending}
              onClick={() => save.mutate([...picked])}
            >
              {save.isPending ? '저장 중…' : '선택 저장'}
            </Button>
            <span className="text-xs text-muted-foreground">
              {saved.size ? `${saved.size}개 골라 둠` : '고른 족보 없음'}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function VoteButton({
  active,
  count,
  label,
  disabled,
  onClick,
  children,
}: {
  active: boolean
  count: number
  label: string
  disabled: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant={active ? 'secondary' : 'ghost'}
      aria-label={label}
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      className={cn('gap-1 px-2', active && 'text-primary')}
    >
      {children}
      <span className="text-xs tabular-nums">{count}</span>
    </Button>
  )
}
