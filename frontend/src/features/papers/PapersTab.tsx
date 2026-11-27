import { useQuery } from '@tanstack/react-query'
import { Minus, Plus } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, unwrap } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { cn } from '@/lib/utils'
import { type PaperSummary, useCreatePaper, usePapers } from './queries'

const STEPS = ['인쇄', '시작', '답안지 사진', '채점', '리포트']

/**
 * 강좌의 '시험' 탭: 종이 시험지 목록과 만들기.
 * paperBase: 시험지 화면 주소 앞부분. 새 디자인 강좌 화면은 '/study/papers', 기존 화면은 '/papers'.
 */
export function PapersTab({ courseId, paperBase = '/papers' }: { courseId: number; paperBase?: string }) {
  const papers = usePapers(courseId)
  const [creating, setCreating] = useState(false)

  return (
    <div className="flex flex-col gap-5">
      <ol
        aria-label="종이 시험 순서"
        className="grid grid-cols-2 gap-x-3 gap-y-2 rounded-2xl bg-navy-tint px-5 py-4 sm:grid-cols-5"
      >
        {STEPS.map((s, i) => (
          <li key={s} className="flex min-w-0 items-center gap-2.5">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-navy text-[13px] font-bold text-white">
              {i + 1}
            </span>
            <span className="text-sm font-bold text-navy">{s}</span>
          </li>
        ))}
      </ol>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold">시험지</h2>
        <button
          type="button"
          onClick={() => setCreating(!creating)}
          aria-expanded={creating}
          className={cn(
            'inline-flex h-11 cursor-pointer items-center gap-2 rounded-full px-5 text-[15px] font-bold',
            creating
              ? 'border border-home-line bg-white text-navy hover:bg-navy-tint'
              : 'bg-navy text-white hover:bg-navy-deep',
          )}
        >
          {creating ? '닫기' : (
            <>
              <Plus size={16} />
              새 시험지 만들기
            </>
          )}
        </button>
      </div>

      {creating && (
        <CreatePaper courseId={courseId} paperBase={paperBase} onDone={() => setCreating(false)} />
      )}

      {papers.isPending ? (
        <Loading />
      ) : !papers.data?.length ? (
        <Empty>아직 시험지가 없습니다. 단원을 골라 첫 시험지를 만들어 보세요.</Empty>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {papers.data.map((p) => (
            <PaperCard key={p.id} p={p} href={`${paperBase}/${p.id}`} />
          ))}
        </div>
      )}
      <ErrorText error={papers.error} />
    </div>
  )
}

function PaperCard({ p, href }: { p: PaperSummary; href: string }) {
  const status = p.my_open_take_id
    ? { label: '푸는 중', cls: 'bg-gold-soft text-[#6b4a0c]', action: '이어서 풀기' }
    : p.my_best != null
      ? { label: '응시함', cls: 'bg-tone-blue text-navy', action: '결과 보기' }
      : { label: '안 풀어 봄', cls: 'bg-home-bg text-ink-2', action: '시작하기' }
  const mcq = p.n_questions - p.n_essay
  return (
    <article className="flex flex-col gap-4 rounded-2xl border border-home-line bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[17px] font-bold">{p.title}</h3>
          <p className="mt-1 text-sm text-ink-2">
            {[mcq > 0 && `객관식 ${mcq}`, p.n_essay > 0 && `서술형 ${p.n_essay}`].filter(Boolean).join(' · ')}{' '}
            · {p.time_limit_min}분 · {p.total_points}점
          </p>
        </div>
        <span className={cn('shrink-0 rounded-full px-2.5 py-1 text-xs font-bold', status.cls)}>
          {status.label}
        </span>
      </div>
      <dl className="grid grid-cols-3 gap-2 rounded-xl bg-home-bg px-4 py-3 text-[13px] text-ink-2">
        <div>
          <dt>만든 사람</dt>
          <dd className="mt-0.5 truncate text-[15px] font-bold text-foreground">
            {p.created_by_me ? '나' : (p.creator_name ?? '알 수 없음')}
          </dd>
        </div>
        <div>
          <dt>응시</dt>
          <dd className="mt-0.5 text-[15px] font-bold text-foreground">{p.takers}명</dd>
        </div>
        <div>
          <dt>내 최고점</dt>
          <dd className="mt-0.5 text-[15px] font-bold text-foreground">
            {p.my_best != null ? `${p.my_best}/${p.total_points}` : '-'}
          </dd>
        </div>
      </dl>
      {/* 응시한 시험지: '결과 보기'는 결과를 바로 열고, '다시 풀기'는 시작 화면으로 */}
      <div className="flex justify-end gap-2">
        {status.action === '결과 보기' && (
          <Link
            to={href}
            className="inline-flex h-11 items-center justify-center rounded-full border border-home-line bg-white px-5 text-[15px] font-bold text-navy hover:bg-navy-tint"
          >
            다시 풀기
          </Link>
        )}
        <Link
          to={status.action === '결과 보기' ? `${href}?view=result` : href}
          className="inline-flex h-11 items-center justify-center rounded-full bg-navy px-5 text-[15px] font-bold text-white hover:bg-navy-deep"
        >
          {status.action}
        </Link>
      </div>
    </article>
  )
}

const FIELD = 'text-xs font-bold text-ink-2'
const INPUT =
  'h-11 rounded-xl border border-home-line bg-white px-3 text-[15px] focus:outline-none focus:ring-2 focus:ring-navy/40'

function CreatePaper({
  courseId,
  paperBase,
  onDone,
}: {
  courseId: number
  paperBase: string
  onDone: () => void
}) {
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
          navigate(`${paperBase}/${p.id}`)
        },
      },
    )
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-5 rounded-2xl border border-home-line bg-white p-5"
    >
      <div className="grid gap-1.5">
        <label htmlFor="ptitle" className={FIELD}>
          제목
        </label>
        <input
          id="ptitle"
          placeholder="모의고사"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className={INPUT}
        />
      </div>

      <fieldset className="grid gap-2">
        <div className="flex items-center justify-between">
          <legend className={FIELD}>범위</legend>
          <button
            type="button"
            className="cursor-pointer text-sm font-bold text-navy hover:underline"
            onClick={() => setPicked(picked.length === usable.length ? [] : usable.map((c) => c.id))}
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
                  aria-pressed={on}
                  disabled={c.problem_count + c.essay_count === 0}
                  onClick={() => setPicked(on ? picked.filter((x) => x !== c.id) : [...picked, c.id])}
                  className={cn(
                    'h-10 cursor-pointer rounded-full border px-4 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-40',
                    on ? 'border-navy bg-navy-tint text-navy' : 'border-home-line bg-white text-ink-2',
                  )}
                >
                  {c.title}
                  <span className="ml-1.5 text-xs font-normal">
                    객{c.problem_count}
                    {c.essay_count > 0 && ` · 서${c.essay_count}`}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-3">
        <CountField id="pmcq" label="객관식" value={mcq} onChange={setMcq} have={picked.length ? haveMcq : null} />
        <CountField id="pessay" label="서술형" value={essay} onChange={setEssay} have={picked.length ? haveEssay : null} />
        <div className="grid gap-1.5">
          <label htmlFor="plimit" className={FIELD}>
            제한 시간(분)
          </label>
          <input
            id="plimit"
            type="number"
            min={5}
            max={300}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className={INPUT}
          />
          <div className="flex gap-1.5">
            {[20, 30, 50, 75].map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setLimit(m)}
                aria-pressed={limit === m}
                className={cn(
                  'h-8 cursor-pointer rounded-full border px-2.5 text-xs font-bold',
                  limit === m ? 'border-navy bg-navy-tint text-navy' : 'border-home-line text-ink-2',
                )}
              >
                {m}분
              </button>
            ))}
          </div>
        </div>
      </div>
      <p className="-mt-2 text-sm text-ink-2">
        고른 단원을 돌아가며 골고루 뽑아요.
        {picked.length > 0 && ` 고른 범위에 객관식 ${haveMcq}개 · 서술형 ${haveEssay}개가 있어요.`}
      </p>

      <ErrorText error={create.error} />
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="submit"
          disabled={!picked.length || mcq + essay === 0 || create.isPending}
          className="h-11 cursor-pointer rounded-full bg-navy px-6 text-[15px] font-bold text-white hover:bg-navy-deep disabled:cursor-not-allowed disabled:opacity-40"
        >
          {create.isPending ? '만드는 중…' : '만들기'}
        </button>
        <button
          type="button"
          onClick={onDone}
          className="h-11 cursor-pointer rounded-full px-4 text-[15px] font-bold text-ink-2 hover:bg-home-bg"
        >
          취소
        </button>
        {picked.length > 0 && (
          <span className="ml-auto text-sm text-ink-2">
            {Math.min(mcq, haveMcq) + Math.min(essay, haveEssay)}문항으로 만들어집니다
          </span>
        )}
      </div>
    </form>
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
  const step = 'flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full border border-home-line bg-white text-navy hover:bg-navy-tint'
  return (
    <div className="grid gap-1.5">
      <label htmlFor={id} className={FIELD}>
        {label} 문항 수
      </label>
      <div className="flex items-center gap-1.5">
        <button type="button" aria-label={`${label} 하나 줄이기`} className={step} onClick={() => onChange(Math.max(0, value - 1))}>
          <Minus size={16} />
        </button>
        <input
          id={id}
          type="number"
          min={0}
          value={value}
          onChange={(e) => onChange(Math.max(0, Number(e.target.value)))}
          className={cn(INPUT, 'w-full min-w-0 text-center')}
        />
        <button type="button" aria-label={`${label} 하나 늘리기`} className={step} onClick={() => onChange(value + 1)}>
          <Plus size={16} />
        </button>
      </div>
      {have != null && value > have && <span className="text-xs text-[#8a6212]">있는 {have}개만 들어갑니다</span>}
    </div>
  )
}
