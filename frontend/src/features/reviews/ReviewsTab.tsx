import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Star } from 'lucide-react'
import { useId, useState } from 'react'
import { api, type Schemas, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'

type Body = Omit<Schemas['ReviewCreate'], 'enrollment_id'>
const PAGE_SIZE = 20
const DIFFICULTY_LABELS = ['매우 쉬움', '쉬움', '보통', '어려움', '매우 어려움']
const RECOMMENDATION_LABELS = ['전혀 추천하지 않음', '추천하지 않음', '보통', '추천함', '매우 추천함']
const WORKLOAD_LABELS = ['매우 적음', '적음', '보통', '많음', '매우 많음']

export function ReviewsTab({ courseId }: { courseId: number }) {
  const qc = useQueryClient()
  const [page, setPage] = useState(0)
  const [writing, setWriting] = useState(false)
  const [deleting, setDeleting] = useState<number | null>(null)
  const key = ['courses', courseId, 'reviews']
  const reviews = useQuery({ queryKey: [...key, page], queryFn: () => unwrap(api.GET('/api/v1/courses/{course_id}/reviews', {
    params: { path: { course_id: courseId }, query: { offset: page * PAGE_SIZE, limit: PAGE_SIZE } },
  })) })
  const terms = useQuery({ queryKey: [...key, 'terms'], queryFn: () => unwrap(api.GET('/api/v1/courses/{course_id}/reviews/terms', {
    params: { path: { course_id: courseId } },
  })) })
  const refresh = () => { void qc.invalidateQueries({ queryKey: key }) }
  const remove = useMutation({
    mutationFn: (id: number) => unwrap(api.DELETE('/api/v1/reviews/{review_id}', { params: { path: { review_id: id } } })),
    onSuccess: () => { setDeleting(null); setPage(0); refresh() },
  })
  const available = (terms.data ?? []).filter(t => t.review_id === null)
  return <section className="flex flex-col gap-4" aria-label="강좌 후기">
    <div className="flex items-center justify-between gap-3">
      <div><h2 className="text-lg font-semibold">수업·시험 후기</h2><p className="text-sm text-muted-foreground">수강한 과목의 경험과 공부 팁을 익명으로 공유해 주세요.</p></div>
      {!writing && available.length > 0 && <Button onClick={() => setWriting(true)}>후기 작성</Button>}
    </div>
    <ErrorText error={terms.error} />
    {terms.data && terms.data.length === 0 && <p className="text-sm text-muted-foreground">이 강좌에 연결된 본인의 수강 기록이 있어야 작성할 수 있습니다.</p>}
    {terms.data && terms.data.length > 0 && available.length === 0 && <p className="text-sm text-muted-foreground">이미 이 강좌의 후기를 작성했어요. 같은 과목·교수의 강좌에는 한 번만 작성할 수 있으며, 삭제 후에도 다시 작성할 수 없습니다.</p>}
    {writing && <ReviewForm courseId={courseId} terms={available}
      onCancel={() => setWriting(false)}
      onSaved={() => { setWriting(false); setPage(0); refresh() }} />}
    {reviews.isPending && <Loading />}
    <ErrorText error={reviews.error} />
    {reviews.data?.length === 0 && <Empty>아직 후기가 없습니다. 첫 수업 경험을 남겨 주세요.</Empty>}
    {reviews.data?.map(r => <Card key={r.id} className="gap-3 p-5">
      <div className="flex flex-wrap justify-between gap-2 text-sm"><span className="font-medium">{r.term} · {r.is_mine ? '내 후기' : '익명'}</span><time dateTime={r.created_at}>{r.created_at.slice(0, 10)}</time></div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span>전체 추천도</span>
        <span className="flex gap-0.5" role="img" aria-label={`추천도 ${r.recommendation}점: ${RECOMMENDATION_LABELS[r.recommendation - 1]}`}>
          {[1, 2, 3, 4, 5].map(n => <Star key={n} aria-hidden="true" className={`size-5 ${n <= r.recommendation ? 'fill-amber-400 text-amber-500' : 'text-muted-foreground/40'}`} />)}
        </span>
        <span>{r.recommendation}/5 · {RECOMMENDATION_LABELS[r.recommendation - 1]}</span>
      </div>
      <p className="text-sm text-muted-foreground">체감 난이도 {r.difficulty}/5 · {DIFFICULTY_LABELS[r.difficulty - 1]} · 과제량 {WORKLOAD_LABELS[r.workload - 1]}</p>
      <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{r.content}</p>
      {r.is_mine && <div className="flex flex-wrap gap-2">
        <Button variant="ghost" disabled={remove.isPending} onClick={() => { setDeleting(r.id); remove.reset() }}>삭제</Button>
        {deleting === r.id && <div className="flex w-full flex-wrap items-center gap-2 rounded border p-3">
          <span className="text-sm">이 후기를 삭제할까요? 삭제 후에는 이 강좌에 다시 작성할 수 없습니다.</span>
          <Button variant="destructive" disabled={remove.isPending} onClick={() => remove.mutate(r.id)}>삭제 확인</Button>
          <Button variant="ghost" disabled={remove.isPending} onClick={() => setDeleting(null)}>취소</Button>
          <ErrorText error={remove.error} />
        </div>}
      </div>}
    </Card>)}
    <div className="flex items-center justify-center gap-3">
      <Button variant="outline" disabled={page === 0 || reviews.isPending} onClick={() => setPage(p => p - 1)}>이전</Button>
      <span className="text-sm">{page + 1}페이지</span>
      <Button variant="outline" disabled={!reviews.data || reviews.data.length < PAGE_SIZE || reviews.isPending} onClick={() => setPage(p => p + 1)}>다음</Button>
    </div>
  </section>
}

function ReviewForm({ courseId, terms, onCancel, onSaved }: {
  courseId: number; terms: Schemas['ReviewTerm'][]; onCancel: () => void; onSaved: () => void
}) {
  const [enrollmentId, setEnrollmentId] = useState(terms[0]?.enrollment_id ?? 0)
  const [content, setContent] = useState('')
  const [difficulty, setDifficulty] = useState(3)
  const [workload, setWorkload] = useState(3)
  const [recommendation, setRecommendation] = useState(3)
  const ratingId = useId()
  const save = useMutation({
    mutationFn: (body: Body) => unwrap(api.POST('/api/v1/courses/{course_id}/reviews', {
      params: { path: { course_id: courseId } }, body: { ...body, enrollment_id: enrollmentId },
    })),
    onSuccess: onSaved,
  })
  const selectClass = 'rounded-md border bg-background px-3 py-2 text-sm'
  return <Card className="p-5"><form className="flex flex-col gap-4" onSubmit={e => { e.preventDefault(); save.mutate({ content: content.trim(), recommendation, difficulty, workload }) }}>
    <h3 className="font-semibold">후기 작성</h3>
    <label className="flex flex-col gap-2 text-sm">수강 학기
      <select className={selectClass} value={enrollmentId} onChange={e => setEnrollmentId(Number(e.target.value))} disabled={save.isPending}>
        {terms.map(t => <option key={t.enrollment_id} value={t.enrollment_id}>{t.term}</option>)}
      </select></label>
    <p className="rounded-md bg-muted p-3 text-sm">같은 과목·교수의 강좌당 한 번만 작성할 수 있고 저장 후 수정할 수 없습니다. 추천도와 내용을 확인한 뒤 저장해 주세요.</p>
    <fieldset disabled={save.isPending} className="min-w-0">
      <legend className="mb-2 text-sm font-medium">전체 추천도</legend>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1">
          {RECOMMENDATION_LABELS.map((label, i) => {
            const value = i + 1
            return <label key={value} className="relative cursor-pointer">
              <input type="radio" name={`${ratingId}-recommendation`} value={value}
                checked={recommendation === value} onChange={() => setRecommendation(value)}
                aria-label={`추천도 ${value}점: ${label}`} className="peer sr-only" />
              <span className="flex size-11 items-center justify-center rounded-md transition-colors hover:bg-amber-50 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary peer-disabled:cursor-not-allowed peer-disabled:opacity-50">
                <Star aria-hidden="true" className={`size-8 ${value <= recommendation ? 'fill-amber-400 text-amber-500' : 'fill-none text-muted-foreground/40'}`} />
              </span>
            </label>
          })}
        </div>
        <span className="text-sm" aria-live="polite">{recommendation}/5 · {RECOMMENDATION_LABELS[recommendation - 1]}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">별이 많을수록 추천하는 수업이에요.</p>
    </fieldset>
    <fieldset disabled={save.isPending} className="min-w-0">
      <legend className="mb-2 text-sm font-medium">체감 난이도</legend>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1">
          {DIFFICULTY_LABELS.map((label, i) => {
            const value = i + 1
            return <label key={value} className="relative cursor-pointer">
              <input type="radio" name={`${ratingId}-difficulty`} value={value}
                checked={difficulty === value} onChange={() => setDifficulty(value)}
                aria-label={`난이도 ${value}점: ${label}`} className="peer sr-only" />
              <span className="flex size-11 items-center justify-center rounded-md transition-colors hover:bg-amber-50 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary peer-disabled:cursor-not-allowed peer-disabled:opacity-50">
                <Star aria-hidden="true" className={`size-8 ${value <= difficulty ? 'fill-amber-400 text-amber-500' : 'fill-none text-muted-foreground/40'}`} />
              </span>
            </label>
          })}
        </div>
        <span className="text-sm" aria-live="polite">{difficulty}/5 · {DIFFICULTY_LABELS[difficulty - 1]}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">별이 많을수록 어려운 수업이에요.</p>
    </fieldset>
    <fieldset disabled={save.isPending} className="min-w-0">
      <legend className="mb-2 text-sm font-medium">과제량</legend>
      <div className="flex flex-wrap gap-2">
        {WORKLOAD_LABELS.map((label, i) => <label key={label} className="relative cursor-pointer">
          <input type="radio" name={`${ratingId}-workload`} value={i + 1}
            checked={workload === i + 1} onChange={() => setWorkload(i + 1)}
            aria-label={`과제량: ${label}`} className="peer sr-only" />
          <span className="flex min-h-11 items-center rounded-md border px-4 py-2 text-sm transition-colors hover:bg-accent peer-checked:border-primary peer-checked:bg-primary peer-checked:font-semibold peer-checked:text-primary-foreground peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary peer-disabled:cursor-not-allowed peer-disabled:opacity-50">{label}</span>
        </label>)}
      </div>
    </fieldset>
    <label className="flex flex-col gap-2 text-sm">수업·시험 후기<Textarea rows={6} minLength={10} maxLength={3000} required value={content} onChange={e => setContent(e.target.value)} disabled={save.isPending} placeholder="시험 유형, 도움이 된 자료, 공부 방법을 알려 주세요. 개인정보나 비방은 포함하지 말아 주세요." /></label>
    <p className="text-xs text-muted-foreground">{content.length}/3000자 · 최소 10자 · 다른 사용자에게 작성자 이름은 표시되지 않습니다.</p>
    <ErrorText error={save.error} />
    <div className="flex gap-2"><Button type="submit" disabled={save.isPending || content.trim().length < 10 || !enrollmentId}>{save.isPending ? '저장 중…' : '저장'}</Button><Button type="button" variant="outline" disabled={save.isPending} onClick={onCancel}>취소</Button></div>
  </form></Card>
}
