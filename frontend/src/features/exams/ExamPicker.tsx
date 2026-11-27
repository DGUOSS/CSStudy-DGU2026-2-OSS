import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ThumbsDown, ThumbsUp } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { type Schemas, api, unwrap } from '@/api/client'
import { ErrorText } from '@/components/States'
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

  // 챕터 목록 위에 붙는 작은 상자라 불러오는 동안은 자리를 차지하지 않는다(큰 '불러오는 중…'이 목록을 밀어냄)
  if (exams.isPending) return null
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
    <div className="flex flex-col gap-2.5">
      <p className="text-[13px] leading-relaxed text-ink-2">
        고른 족보는 새 문제를 만들 때 출제 스타일 참고로 써요. 좋아요가 많은 족보가 위에 와요.
      </p>
      {exams.data.length === 0 ? (
        <p className="rounded-xl bg-home-bg px-3 py-2.5 text-[13px] text-ink-2">
          아직 올라온 족보가 없어요. 자료의 '족보'에서 올려 주세요.
        </p>
      ) : (
          <ul className="flex flex-col divide-y divide-home-line overflow-hidden rounded-xl border border-home-line bg-white">
            {exams.data.map((e) => (
              <li key={e.id} className="flex items-center gap-2 px-3 py-2">
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={picked.has(e.id)}
                  aria-label={`${e.title} 선택`}
                  onClick={() => toggle(e.id)}
                  className={cn(
                    'flex size-5 shrink-0 cursor-pointer items-center justify-center rounded-md border border-home-line bg-white',
                    picked.has(e.id) && 'border-navy bg-navy text-white',
                  )}
                >
                  {picked.has(e.id) && <Check className="size-3.5" />}
                </button>
                <button
                  type="button"
                  onClick={() => toggle(e.id)}
                  className="min-w-0 flex-1 cursor-pointer text-left"
                >
                  <div className="truncate text-sm font-bold">{e.title}</div>
                  <div className="truncate text-xs text-ink-2">
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
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-ink-2">{saved.size ? `${saved.size}개 골라 둠` : '고른 족보 없음'}</span>
          <button
            type="button"
            disabled={!dirty || save.isPending}
            onClick={() => save.mutate([...picked])}
            className="h-9 cursor-pointer rounded-full bg-navy px-4 text-sm font-bold text-white hover:bg-navy-deep disabled:cursor-default disabled:opacity-40"
          >
            {save.isPending ? '저장 중…' : '선택 저장'}
          </button>
        </div>
      )}
    </div>
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
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'inline-flex h-8 shrink-0 cursor-pointer items-center gap-1 rounded-full px-2 text-ink-2 hover:bg-home-bg disabled:opacity-50 [&_svg]:size-3.5',
        active && 'bg-navy-tint text-navy',
      )}
    >
      {children}
      <span className="text-xs font-bold tabular-nums">{count}</span>
    </button>
  )
}
