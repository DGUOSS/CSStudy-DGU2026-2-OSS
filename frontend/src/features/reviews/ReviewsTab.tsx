import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PenLine, Star } from 'lucide-react'
import { useId, useState } from 'react'
import { api, type Schemas, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { cn } from '@/lib/utils'

type Body = Omit<Schemas['ReviewCreate'], 'enrollment_id'>
const PAGE_SIZE = 20
const DIFFICULTY_LABELS = ['매우 쉬움', '쉬움', '보통', '어려움', '매우 어려움']
const RECOMMENDATION_LABELS = ['전혀 추천하지 않음', '추천하지 않음', '보통', '추천함', '매우 추천함']
const WORKLOAD_LABELS = ['매우 적음', '적음', '보통', '많음', '매우 많음']
const TEAM_CHOICES: { value: boolean | null; label: string }[] = [
  { value: true, label: '있었어요' },
  { value: false, label: '없었어요' },
  { value: null, label: '답하지 않음' },
]

// 새 디자인 모양 (다른 화면과 같은 카드·버튼)
const CARD = 'rounded-2xl border border-home-line bg-white'
const BTN = {
  primary:
    'inline-flex h-11 cursor-pointer items-center justify-center gap-1.5 rounded-full bg-navy px-5 text-[15px] font-bold text-white hover:bg-navy-deep disabled:cursor-default disabled:opacity-50',
  line: 'inline-flex h-11 cursor-pointer items-center justify-center rounded-full border border-home-line bg-white px-5 text-[15px] font-bold text-navy hover:bg-navy-tint disabled:cursor-default disabled:opacity-50',
  quiet:
    'inline-flex h-9 cursor-pointer items-center justify-center rounded-full px-3 text-sm font-bold text-ink-2 hover:bg-home-bg hover:text-navy disabled:cursor-default disabled:opacity-50',
}
const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null)

function Stars({ value, size = 'size-5' }: { value: number; size?: string }) {
  return (
    <span className="flex gap-0.5" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star key={n} className={cn(size, n <= Math.round(value) ? 'fill-gold text-gold' : 'text-[#d9dee8]')} />
      ))}
    </span>
  )
}

export function ReviewsTab({ courseId, readOnly = false }: { courseId: number; readOnly?: boolean }) {
  const qc = useQueryClient()
  const [page, setPage] = useState(0)
  const [writing, setWriting] = useState(false)
  const [deleting, setDeleting] = useState<number | null>(null)
  const key = ['courses', courseId, 'reviews']
  const reviews = useQuery({
    queryKey: [...key, page],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/courses/{course_id}/reviews', {
          params: { path: { course_id: courseId }, query: { offset: page * PAGE_SIZE, limit: PAGE_SIZE } },
        }),
      ),
  })
  const terms = useQuery({
    enabled: !readOnly,
    queryKey: [...key, 'terms'],
    queryFn: () =>
      unwrap(api.GET('/api/v1/courses/{course_id}/reviews/terms', { params: { path: { course_id: courseId } } })),
  })
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: key })
    void qc.invalidateQueries({ queryKey: ['courses', courseId, 'team-project'] })
  }
  const remove = useMutation({
    mutationFn: (id: number) => unwrap(api.DELETE('/api/v1/reviews/{review_id}', { params: { path: { review_id: id } } })),
    onSuccess: () => {
      setDeleting(null)
      setPage(0)
      refresh()
    },
  })
  const available = (terms.data ?? []).filter((t) => t.review_id === null)
  const list = reviews.data ?? []
  // 요약: 이 쪽에 받아 온 후기(최대 20개) 기준
  const rec = avg(list.map((r) => r.recommendation))
  const dif = avg(list.map((r) => r.difficulty))
  const wl = avg(list.map((r) => r.workload))
  const hint =
    terms.data && terms.data.length === 0
      ? '이 강좌를 수강한 기록이 있어야 후기를 쓸 수 있어요.'
      : terms.data && terms.data.length > 0 && available.length === 0
        ? '이 강좌 후기를 이미 썼어요. 강좌마다 한 번만 쓸 수 있어요.'
        : null

  return (
    <section className="flex flex-col gap-4" aria-label="강좌 후기">
      {/* 요약 + 쓰기 */}
      <div className={cn(CARD, 'flex flex-wrap items-center gap-x-8 gap-y-4 p-5')}>
        {rec != null ? (
          <>
            <div className="flex items-center gap-3">
              <span className="text-4xl leading-none font-bold tabular-nums">{rec.toFixed(1)}</span>
              <div>
                <Stars value={rec} />
                <p className="mt-1 text-[13px] text-ink-2">
                  추천도 · 후기 {list.length}
                  {list.length === PAGE_SIZE && '+'}개
                </p>
              </div>
            </div>
            <dl className="flex gap-6 text-sm">
              <div>
                <dt className="text-[13px] text-ink-2">체감 난이도</dt>
                <dd className="mt-0.5 font-bold">{DIFFICULTY_LABELS[Math.round(dif!) - 1]}</dd>
              </div>
              <div>
                <dt className="text-[13px] text-ink-2">과제량</dt>
                <dd className="mt-0.5 font-bold">{WORKLOAD_LABELS[Math.round(wl!) - 1]}</dd>
              </div>
            </dl>
          </>
        ) : (
          <p className="text-[15px] font-bold text-ink-2">아직 후기가 없어요</p>
        )}
        {!readOnly && <div className="ml-auto flex flex-col items-end gap-1">
          {!writing && available.length > 0 && (
            <button type="button" className={BTN.primary} onClick={() => setWriting(true)}>
              <PenLine size={16} aria-hidden="true" /> 후기 쓰기
            </button>
          )}
          {hint && <p className="text-[13px] text-ink-2">{hint}</p>}
        </div>}
      </div>
      {!readOnly && <ErrorText error={terms.error} />}

      {!readOnly && writing && (
        <ReviewForm
          courseId={courseId}
          terms={available}
          onCancel={() => setWriting(false)}
          onSaved={() => {
            setWriting(false)
            setPage(0)
            refresh()
          }}
        />
      )}

      {reviews.isPending && <Loading />}
      <ErrorText error={reviews.error} />
      {!readOnly && reviews.data?.length === 0 && <Empty>아직 후기가 없어요. 첫 수업 경험을 남겨 주세요.</Empty>}
      {list.length > 0 && (
        <ul className={cn(CARD, 'divide-y divide-home-line overflow-hidden')}>
          {list.map((r) => (
            <li key={r.id} className={cn('flex flex-col gap-2.5 px-5 py-4', r.is_mine && 'bg-navy-tint/50')}>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span
                  role="img"
                  aria-label={`추천도 ${r.recommendation}점: ${RECOMMENDATION_LABELS[r.recommendation - 1]}`}
                >
                  <Stars value={r.recommendation} size="size-4" />
                </span>
                <span className="text-sm font-bold">{RECOMMENDATION_LABELS[r.recommendation - 1]}</span>
                <span className="text-[13px] text-ink-2">
                  {r.term} · {r.is_mine ? <b className="text-navy">내 후기</b> : '익명'}
                </span>
                <time className="ml-auto text-[13px] text-ink-2" dateTime={r.created_at}>
                  {r.created_at.slice(0, 10)}
                </time>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Chip>난이도 {DIFFICULTY_LABELS[r.difficulty - 1]}</Chip>
                <Chip>과제 {WORKLOAD_LABELS[r.workload - 1]}</Chip>
                {r.team_project != null && <Chip>팀플 {r.team_project ? '있음' : '없음'}</Chip>}
              </div>
              <p className="text-[15px] leading-relaxed whitespace-pre-wrap break-words">{r.content}</p>
              {!readOnly && r.is_mine &&
                (deleting === r.id ? (
                  <div className="flex flex-wrap items-center gap-2 rounded-xl bg-white p-3">
                    <span className="mr-auto text-sm">삭제하면 이 강좌에 다시 쓸 수 없어요. 삭제할까요?</span>
                    <button type="button" className={BTN.quiet} disabled={remove.isPending} onClick={() => setDeleting(null)}>
                      취소
                    </button>
                    <button
                      type="button"
                      className="inline-flex h-9 cursor-pointer items-center rounded-full bg-[#c8453f] px-4 text-sm font-bold text-white hover:bg-[#b03a35] disabled:opacity-50"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(r.id)}
                    >
                      삭제
                    </button>
                    <ErrorText error={remove.error} />
                  </div>
                ) : (
                  <button
                    type="button"
                    className={cn(BTN.quiet, 'self-end')}
                    disabled={remove.isPending}
                    onClick={() => {
                      setDeleting(r.id)
                      remove.reset()
                    }}
                  >
                    삭제
                  </button>
                ))}
            </li>
          ))}
        </ul>
      )}
      {(page > 0 || list.length === PAGE_SIZE) && (
        <nav aria-label="후기 쪽" className="flex items-center justify-center gap-2">
          <button
            type="button"
            className={BTN.quiet}
            disabled={page === 0 || reviews.isPending}
            onClick={() => setPage((p) => p - 1)}
          >
            이전
          </button>
          <span className="text-sm text-ink-2 tabular-nums">{page + 1}쪽</span>
          <button
            type="button"
            className={BTN.quiet}
            disabled={!reviews.data || reviews.data.length < PAGE_SIZE || reviews.isPending}
            onClick={() => setPage((p) => p + 1)}
          >
            다음
          </button>
        </nav>
      )}
    </section>
  )
}

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full bg-home-bg px-2.5 py-0.5 text-xs font-bold text-ink-2">{children}</span>
}

/** 별 다섯 개 고르기 (추천도·난이도) */
function StarPicker({
  name,
  value,
  onChange,
  labels,
  aria,
}: {
  name: string
  value: number
  onChange: (v: number) => void
  labels: string[]
  aria: string
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex gap-0.5">
        {labels.map((label, i) => {
          const v = i + 1
          return (
            <label key={v} className="relative cursor-pointer">
              <input
                type="radio"
                name={name}
                value={v}
                checked={value === v}
                onChange={() => onChange(v)}
                aria-label={`${aria} ${v}점: ${label}`}
                className="peer sr-only"
              />
              <span className="flex size-10 items-center justify-center rounded-lg transition-colors peer-hover:bg-gold-soft/60 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-navy peer-disabled:cursor-not-allowed peer-disabled:opacity-50">
                <Star aria-hidden="true" className={cn('size-7', v <= value ? 'fill-gold text-gold' : 'text-[#d9dee8]')} />
              </span>
            </label>
          )
        })}
      </div>
      <span className="text-sm font-bold" aria-live="polite">
        {labels[value - 1]}
      </span>
    </div>
  )
}

/** 하나 고르기 (과제량·팀플): 알약 모양 버튼 줄 */
function PillPicker<T>({
  name,
  value,
  onChange,
  options,
  aria,
}: {
  name: string
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
  aria: string
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <label key={o.label} className="relative cursor-pointer">
          <input
            type="radio"
            name={name}
            checked={value === o.value}
            onChange={() => onChange(o.value)}
            aria-label={`${aria}: ${o.label}`}
            className="peer sr-only"
          />
          <span className="flex h-10 items-center rounded-full border border-home-line bg-white px-4 text-sm font-bold text-ink-2 transition-colors hover:text-navy peer-checked:border-navy peer-checked:bg-navy peer-checked:text-white peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-navy peer-disabled:cursor-not-allowed peer-disabled:opacity-50">
            {o.label}
          </span>
        </label>
      ))}
    </div>
  )
}

function ReviewForm({
  courseId,
  terms,
  onCancel,
  onSaved,
}: {
  courseId: number
  terms: Schemas['ReviewTerm'][]
  onCancel: () => void
  onSaved: () => void
}) {
  const [enrollmentId, setEnrollmentId] = useState(terms[0]?.enrollment_id ?? 0)
  const [content, setContent] = useState('')
  const [difficulty, setDifficulty] = useState(3)
  const [workload, setWorkload] = useState(3)
  const [recommendation, setRecommendation] = useState(3)
  const [teamProject, setTeamProject] = useState<boolean | null>(null)
  const id = useId()
  const save = useMutation({
    mutationFn: (body: Body) =>
      unwrap(
        api.POST('/api/v1/courses/{course_id}/reviews', {
          params: { path: { course_id: courseId } },
          body: { ...body, enrollment_id: enrollmentId },
        }),
      ),
    onSuccess: onSaved,
  })
  const field = 'text-sm font-bold'
  return (
    <form
      className={cn(CARD, 'flex flex-col gap-5 p-6')}
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate({ content: content.trim(), recommendation, difficulty, workload, team_project: teamProject })
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-bold">후기 쓰기</h3>
        {terms.length > 1 ? (
          <label className="flex items-center gap-2 text-sm font-bold">
            수강 학기
            <select
              className="h-10 rounded-xl border border-home-line bg-white px-3 text-sm"
              value={enrollmentId}
              onChange={(e) => setEnrollmentId(Number(e.target.value))}
              disabled={save.isPending}
            >
              {terms.map((t) => (
                <option key={t.enrollment_id} value={t.enrollment_id}>
                  {t.term}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className="text-sm text-ink-2">{terms[0]?.term} 수강</span>
        )}
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <fieldset disabled={save.isPending} className="min-w-0">
          <legend className={cn(field, 'mb-1.5')}>추천도</legend>
          <StarPicker
            name={`${id}-rec`}
            value={recommendation}
            onChange={setRecommendation}
            labels={RECOMMENDATION_LABELS}
            aria="추천도"
          />
        </fieldset>
        <fieldset disabled={save.isPending} className="min-w-0">
          <legend className={cn(field, 'mb-1.5')}>체감 난이도</legend>
          <StarPicker name={`${id}-dif`} value={difficulty} onChange={setDifficulty} labels={DIFFICULTY_LABELS} aria="난이도" />
        </fieldset>
        <fieldset disabled={save.isPending} className="min-w-0">
          <legend className={cn(field, 'mb-1.5')}>과제량</legend>
          <PillPicker
            name={`${id}-wl`}
            value={workload}
            onChange={setWorkload}
            options={WORKLOAD_LABELS.map((label, i) => ({ value: i + 1, label }))}
            aria="과제량"
          />
        </fieldset>
        <fieldset disabled={save.isPending} className="min-w-0">
          <legend className={cn(field, 'mb-1.5')}>팀 프로젝트가 있었나요?</legend>
          <PillPicker name={`${id}-team`} value={teamProject} onChange={setTeamProject} options={TEAM_CHOICES} aria="팀 프로젝트" />
        </fieldset>
      </div>

      <label className={cn(field, 'flex flex-col gap-1.5')}>
        후기
        <textarea
          rows={5}
          minLength={10}
          maxLength={3000}
          required
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={save.isPending}
          placeholder="시험 유형, 도움이 된 자료, 공부 방법을 알려 주세요."
          className="rounded-xl border border-home-line bg-white px-3.5 py-3 text-[15px] font-normal leading-relaxed focus-visible:outline-2 focus-visible:outline-navy"
        />
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-[13px] text-ink-2">
          {content.length}/3000자 · 이름은 안 보여요 · 저장하면 고칠 수 없어요
        </p>
        <ErrorText error={save.error} />
        <button type="button" className={BTN.line} disabled={save.isPending} onClick={onCancel}>
          취소
        </button>
        <button
          type="submit"
          className={BTN.primary}
          disabled={save.isPending || content.trim().length < 10 || !enrollmentId}
        >
          {save.isPending ? '저장 중…' : '저장'}
        </button>
      </div>
    </form>
  )
}
