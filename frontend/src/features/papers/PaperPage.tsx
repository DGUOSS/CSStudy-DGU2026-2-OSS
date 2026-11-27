import {
  Camera,
  Check,
  ChevronLeft,
  Clock,
  Download,
  Loader2,
  Maximize2,
  Minimize2,
  Pause,
  Pencil,
  Play,
  Printer,
  RotateCcw,
  Sparkles,
  Trophy,
  X,
} from 'lucide-react'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router'
import type { Schemas } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Evidence } from '@/features/problems/Evidence'
import { cn } from '@/lib/utils'
import {
  mmss,
  type Paper,
  type Take,
  useAbandon,
  useMine,
  usePause,
  usePaper,
  useRanking,
  useResume,
  useScan,
  useSheet,
  useStartTake,
  useSubmit,
  useTakeResult,
} from './queries'
import { downloadSheetPngs } from './sheetImage'

const ReportCharts = lazy(() => import('./Report'))

/** 종이 시험: 인쇄 → [시험 시작] → 타이머 → 답안지 사진 → 인식 결과 확인 → 채점 → 등수 */
export function PaperPage() {
  const paperId = Number(useParams().paperId)
  const paper = usePaper(paperId)
  const mine = useMine(paperId)
  const start = useStartTake(paperId)
  // 목록의 '결과 보기'는 ?view=result로 온다 → 가장 최근 제출 결과를 바로 연다
  const [params, setParams] = useSearchParams()
  const [picked, setPicked] = useState<number | null>(null)
  const latest = mine.data?.submitted[0]?.take_id ?? null
  const viewTake = picked ?? (params.get('view') === 'result' ? latest : null)
  const setViewTake = (id: number | null) => {
    setPicked(id)
    if (id === null && params.has('view')) setParams({}, { replace: true })
  }
  // 새 디자인 틀(/study/papers/:id)에서 열었으면 새 강좌 화면으로 돌아간다
  const inStudy = useLocation().pathname.startsWith('/study/')

  if (paper.isPending || mine.isPending) return <Loading />
  if (!paper.data || !mine.data) return <ErrorText error={paper.error ?? mine.error} />
  const p = paper.data
  const open = mine.data.open_take

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          to={inStudy ? `/study/courses/${p.course_id}?tab=papers` : `/courses/${p.course_id}?tab=papers`}
          className="mb-2 inline-flex items-center text-sm text-ink-2 hover:text-navy"
        >
          <ChevronLeft className="size-4" />
          시험 목록
        </Link>
        <h1 className="text-2xl font-bold">{p.title}</h1>
        <p className="mt-1 text-sm text-ink-2">
          시험지 #{p.id} · {p.problems.length}문항 · {p.total_points}점 · 제한 시간{' '}
          {p.time_limit_min}분
        </p>
      </div>

      {open ? (
        <Running
          key={open.id}
          paper={p}
          take={open}
          fetchedAt={mine.dataUpdatedAt}
          onDone={(id) => setViewTake(id)}
        />
      ) : viewTake ? (
        <ResultView takeId={viewTake} onBack={() => setViewTake(null)} />
      ) : (
        <section className={cn(CARD, 'flex flex-col gap-5 p-6')}>
          <ol className="flex flex-col gap-3 text-sm leading-relaxed">
            {[
              '시험지를 인쇄합니다(마지막 장이 답안지). 인쇄가 안 되면 답안지 이미지를 받아 그림판이나 태블릿에서 표시해도 됩니다.',
              '준비되면 [시험 시작]을 누릅니다. 문제는 시작한 뒤 이 화면에서도 볼 수 있습니다. 답은 답안지 동그라미에 칠하고, 서술형은 답 칸에 씁니다.',
              '끝나면 답안지를 사진(또는 이미지 파일)으로 올리고, 인식된 답을 확인해 제출합니다.',
            ].map((text, i) => (
              <li key={i} className="flex gap-3">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-navy text-[13px] font-bold text-white">
                  {i + 1}
                </span>
                <span className="pt-1">{text}</span>
              </li>
            ))}
          </ol>
          <div className="flex flex-wrap justify-end gap-2">
            <Link
              to={inStudy ? `/study/papers/${p.id}/print` : `/papers/${p.id}/print`}
              className={BTN.line}
            >
              <Printer />
              문제지·답안지 인쇄 / PDF
            </Link>
            <SheetDownload paperId={p.id} />
            <button type="button" onClick={() => start.mutate()} disabled={start.isPending} className={BTN.primary}>
              <Clock />
              시험 시작
            </button>
          </div>
          <ErrorText error={start.error} />
        </section>
      )}

      {!open && mine.data.submitted.length > 0 && (
        <div className="flex flex-col gap-2">
          <h2 className="text-xl font-bold">내 응시</h2>
          {mine.data.submitted.map((t, i) => (
            <button
              key={t.take_id}
              type="button"
              onClick={() => setViewTake(t.take_id)}
              className="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-home-line bg-white px-4 py-3 text-left text-sm hover:bg-navy-tint"
            >
              <span>
                {i === mine.data.submitted.length - 1
                  ? '첫 응시'
                  : `${mine.data.submitted.length - i}번째`}{' '}
                · {new Date(t.submitted_at).toLocaleString('ko-KR', { month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
              </span>
              <span>
                <b>
                  {t.score}/{t.total_points}
                </b>
                {t.essay_pending && ' (서술형 채점 대기)'} · {mmss(t.elapsed_sec)}
                {t.late && ' · 시간 초과'}
                <span className="ml-3 font-bold text-navy">결과 보기 ›</span>
              </span>
            </button>
          ))}
        </div>
      )}

      <Ranking paperId={p.id} />
    </div>
  )
}

function Running({
  paper,
  take,
  fetchedAt,
  onDone,
}: {
  paper: Paper
  take: Take
  fetchedAt: number
  onDone: (takeId: number) => void
}) {
  const pause = usePause(paper.id)
  const resume = useResume(paper.id)
  const abandon = useAbandon(paper.id)
  const [now, setNow] = useState(() => Date.now())
  const [submitting, setSubmitting] = useState(false)
  const [big, setBig] = useState(false)
  const busy = pause.isPending || resume.isPending || abandon.isPending

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(t)
  }, [])
  // 서버가 알려 준 남은 시간에서, 받은 뒤 흐른 시간을 뺀다(멈춘 동안은 그대로)
  const left = take.paused
    ? take.remaining_sec
    : take.remaining_sec - Math.max(0, (now - fetchedAt) / 1000)
  const over = left <= 0
  const level = over ? 'over' : left <= 60 ? 'last' : left <= 300 ? 'warn' : 'ok'
  const spentRatio = Math.min(1, 1 - Math.max(0, left) / take.time_limit_sec)

  // 탭 제목에 남은 시간, 시간이 다 되면 진동 한 번
  const overRef = useRef(over)
  useEffect(() => {
    const prev = document.title
    document.title = `${take.paused ? '⏸' : '⏱'} ${mmss(Math.max(0, left))} · ${paper.title}`
    return () => {
      document.title = prev
    }
  }, [left, take.paused, paper.title])
  useEffect(() => {
    if (over && !overRef.current) navigator.vibrate?.([300, 150, 300])
    overRef.current = over
  }, [over])
  // 푸는 동안 화면이 꺼지지 않게(지원하는 브라우저만)
  useEffect(() => {
    if (take.paused || over) return
    let lock: { release: () => Promise<void> } | null = null
    const nav = navigator as Navigator & {
      wakeLock?: { request: (t: 'screen') => Promise<{ release: () => Promise<void> }> }
    }
    nav.wakeLock
      ?.request('screen')
      .then((l) => (lock = l))
      .catch(() => {})
    return () => {
      lock?.release().catch(() => {})
    }
  }, [take.paused, over])

  const color =
    level === 'over' || level === 'last'
      ? 'text-[#c8453f]'
      : level === 'warn'
        ? 'text-[#8a6212]'
        : 'text-navy'

  const timer = (
    <div className={cn('flex flex-col items-center gap-2', big && 'gap-6')}>
      <div className={cn('text-sm font-bold text-ink-2', big && 'text-xl')}>
        {take.paused ? '일시정지됨' : over ? '시간이 끝났습니다' : '남은 시간'}
      </div>
      <div
        className={cn(
          'font-mono font-bold tabular-nums transition-colors',
          big ? 'text-[22vw] leading-none' : 'text-6xl',
          color,
          take.paused && 'opacity-40',
        )}
      >
        {over ? `+${mmss(-left)}` : mmss(left)}
      </div>
      <div
        className={cn(
          'h-2 w-full max-w-md overflow-hidden rounded-full bg-[#e6eaf2]',
          big && 'h-3 max-w-3xl',
        )}
      >
        <div
          className={cn(
            'h-full transition-[width]',
            level === 'ok' ? 'bg-navy' : level === 'warn' ? 'bg-gold' : 'bg-[#c8453f]',
          )}
          style={{ width: `${spentRatio * 100}%` }}
        />
      </div>
      <div className={cn('text-center text-sm text-ink-2', big && 'text-base')}>
        {take.paused
          ? '멈춘 동안은 시간이 흐르지 않습니다. 등수표에는 일시정지를 썼다고 표시됩니다.'
          : over
            ? `펜을 내려놓고 답안지를 찍어 제출하세요. ${GRACE}분이 넘으면 시간 초과로 표시됩니다.`
            : level === 'last'
              ? '1분 남았습니다'
              : level === 'warn'
                ? '5분 남았습니다'
                : '종이에 푸세요. 다 풀었으면 바로 제출해도 됩니다(걸린 시간이 등수에 들어갑니다).'}
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {take.paused ? (
          <button type="button" className={BTN.primary} disabled={busy} onClick={() => resume.mutate(take.id)}>
            <Play />
            계속 풀기
          </button>
        ) : (
          !over && (
            <button type="button" className={BTN.line} disabled={busy} onClick={() => pause.mutate(take.id)}>
              <Pause />
              일시정지
            </button>
          )
        )}
        <button
          type="button"
          className={BTN.quiet}
          disabled={busy}
          onClick={() => {
            if (!confirm('처음부터 다시 할까요? 이번 응시는 기록되지 않고, [시험 시작]을 누르면 새로 시작합니다.'))
              return
            if (big) {
              setBig(false)
              if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
            }
            abandon.mutate(take.id)
          }}
        >
          <RotateCcw />
          처음부터 다시
        </button>
        <button
          type="button"
          className={BTN.line}
          onClick={() => {
            setBig(!big)
            if (!big) document.documentElement.requestFullscreen?.().catch(() => {})
            else if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
          }}
        >
          {big ? <Minimize2 /> : <Maximize2 />}
          {big ? '작게 보기' : '크게 보기'}
        </button>
        {!submitting && (
          <button
            type="button"
            className={BTN.primary}
            onClick={() => {
              setSubmitting(true)
              if (big) {
                setBig(false)
                if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
              }
            }}
          >
            <Camera />
            답안지 제출하기
          </button>
        )}
      </div>
    </div>
  )

  return (
    <div className="flex flex-col gap-4">
      {!big && <TakeSteps step={submitting ? 2 : 1} />}
      {big ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-home-bg p-6">
          {timer}
        </div>
      ) : (
        <section className={cn(CARD, 'p-6', over && 'border-[#c8453f]')}>{timer}</section>
      )}
      <ErrorText error={pause.error ?? resume.error ?? abandon.error} />
      {!big && !submitting && <Questions paper={paper} />}
      {submitting && (
        <ScanReview
          paper={paper}
          take={take}
          onDone={onDone}
          onCancel={() => setSubmitting(false)}
        />
      )}
    </div>
  )
}

const GRACE = 10

// 새 디자인 모양 (퀴즈·스터디 화면과 같은 버튼·카드)
const CARD = 'rounded-2xl border border-home-line bg-white'
const BTN = {
  primary:
    'inline-flex h-11 cursor-pointer items-center justify-center gap-1.5 rounded-full bg-navy px-5 text-[15px] font-bold text-white hover:bg-navy-deep disabled:cursor-default disabled:opacity-50 [&_svg]:size-4',
  line: 'inline-flex h-11 cursor-pointer items-center justify-center gap-1.5 rounded-full border border-home-line bg-white px-5 text-[15px] font-bold text-navy hover:bg-navy-tint disabled:cursor-default disabled:opacity-50 [&_svg]:size-4',
  quiet:
    'inline-flex h-11 cursor-pointer items-center justify-center gap-1.5 rounded-full px-4 text-[15px] font-bold text-ink-2 hover:bg-home-bg hover:text-navy disabled:cursor-default disabled:opacity-50 [&_svg]:size-4',
}
const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧']

/** 응시 중 어느 단계인지: 1 종이에 풀기 → 2 답안지 사진·인식 확인 → 3 제출 */
function TakeSteps({ step }: { step: 1 | 2 }) {
  const steps = ['종이에 풀기', '답안지 사진 올리기', '인식 확인 후 제출']
  return (
    <ol aria-label="진행 단계" className="flex flex-wrap gap-2">
      {steps.map((s, i) => {
        const n = i + 1
        const done = n < step
        const now = n === step
        return (
          <li
            key={s}
            aria-current={now ? 'step' : undefined}
            className={cn(
              'flex h-9 items-center gap-1.5 rounded-full px-3.5 text-sm font-bold',
              done && 'bg-tone-blue text-navy',
              now && 'bg-navy text-white',
              !done && !now && 'border border-home-line bg-white text-ink-2',
            )}
          >
            {done ? <Check className="size-4" aria-hidden="true" /> : `${n}.`} {s}
          </li>
        )
      })}
    </ol>
  )
}

/** 시험 중 화면에서 보는 문제(인쇄를 못 했을 때). 정답은 없다. */
function Questions({ paper }: { paper: Paper }) {
  const [open, setOpen] = useState(true)
  return (
    <section className={cn(CARD, 'flex flex-col gap-3 p-6')}>
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">
          문제 <span className="text-[15px] font-normal text-ink-2">{paper.problems.length}문항</span>
        </h2>
        <button type="button" className={cn(BTN.quiet, 'h-9')} onClick={() => setOpen(!open)}>
          {open ? '접기' : '펼치기'}
        </button>
      </div>
      {open && (
        <ol className="flex flex-col gap-5 text-[15px] leading-relaxed">
          {paper.problems.map((q) => (
            <li key={q.id}>
              <div className="whitespace-pre-wrap">
                <b>{q.no}.</b> {q.question}{' '}
                <span className="text-xs text-ink-2">
                  ({q.points}점{q.qtype !== 'mcq' && ' · 서술형, 답안지 칸에 쓰세요'})
                </span>
              </div>
              {q.qtype === 'mcq' && (
                <div className="mt-1.5 grid gap-1 pl-5 text-ink-2">
                  {q.choices.map((c, i) => (
                    <div key={i} className="whitespace-pre-wrap">
                      {CIRCLED[i]} {c}
                    </div>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function SheetDownload({ paperId }: { paperId: number }) {
  const sheet = useSheet(paperId)
  return (
    <button
      type="button"
      className={BTN.line}
      disabled={!sheet.data}
      title="인쇄할 수 없을 때: 그림판·태블릿에서 칠하고 쓴 뒤 그대로 올리거나 화면을 찍어 올리세요"
      onClick={() => sheet.data && downloadSheetPngs(sheet.data.pages, paperId)}
    >
      <Download />
      답안지 이미지 받기
    </button>
  )
}

type Review = { mcq: Schemas['ScanMcq'][]; essays: Schemas['ScanEssay'][]; missing: number[] }

function ScanReview({
  paper,
  take,
  onDone,
  onCancel,
}: {
  paper: Paper
  take: Take
  onDone: (takeId: number) => void
  onCancel: () => void
}) {
  const scan = useScan(take.id)
  const submit = useSubmit(take.id, paper.id)
  const [review, setReview] = useState<Review | null>(null)
  const byId = new Map(paper.problems.map((q) => [q.id, q]))

  const [fileError, setFileError] = useState('')
  const onFiles = (files: FileList | null) => {
    if (!files?.length) return
    const list = Array.from(files)
    const bad = list.filter((f) => !f.type.startsWith('image/'))
    if (bad.length) {
      setFileError(
        `${bad.map((f) => f.name).join(', ')}: 사진 파일이 아닙니다. 디스코드·카톡에서 끌어다 놓으면 바로가기(.url)가 생길 수 있으니, 사진을 '다른 이름으로 저장'한 뒤 올려 주세요.`,
      )
      return
    }
    setFileError('')
    scan.mutate(list, {
      onSuccess: (r) => setReview({ mcq: r.mcq, essays: r.essays, missing: r.missing_pages }),
    })
  }
  const manual = () =>
    setReview({
      mcq: paper.problems
        .filter((q) => q.qtype === 'mcq')
        .map((q) => ({ no: q.no, problem_id: q.id, chosen: null, status: 'blank' })),
      essays: paper.problems
        .filter((q) => q.qtype !== 'mcq')
        .map((q) => ({ no: q.no, problem_id: q.id, image: null })),
      missing: [],
    })
  const pick = (no: number, chosen: number | null) =>
    review &&
    setReview({
      ...review,
      mcq: review.mcq.map((m) =>
        m.no === no ? { ...m, chosen, status: chosen == null ? 'blank' : 'ok' } : m,
      ),
    })
  const send = () =>
    review &&
    submit.mutate(
      {
        answers: review.mcq.map((m) => ({ problem_id: m.problem_id, chosen: m.chosen })),
        essays: review.essays.map((e) => ({ problem_id: e.problem_id, image: e.image })),
      },
      { onSuccess: (r) => onDone(r.take_id) },
    )
  const needCheck = review?.mcq.filter((m) => m.status !== 'ok').length ?? 0

  return (
    <section className={cn(CARD, 'flex flex-col gap-4 p-6')}>
      <div>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">답안지 사진</h2>
          <button type="button" className={cn(BTN.quiet, 'h-9')} onClick={onCancel}>
            계속 풀기
          </button>
        </div>
        <p className="mt-1 text-sm text-ink-2">
          네 귀퉁이의 검은 네모가 모두 나오게, 밝은 곳에서 위에서 찍어 주세요. 답안지가 여러 장이면
          장마다 한 장씩 함께 올립니다.
        </p>
      </div>
      <label
        className={cn(
          'flex cursor-pointer flex-col items-center gap-1.5 rounded-2xl border-2 border-dashed border-home-line bg-home-bg px-4 py-8 text-[15px] hover:border-navy hover:bg-navy-tint',
          scan.isPending && 'pointer-events-none opacity-60',
        )}
      >
        <Camera className="size-7 text-navy" />
        <span className="font-bold text-navy">
          {scan.isPending ? '읽는 중…' : review ? '다시 찍기' : '답안지 찍기 / 사진 고르기'}
        </span>
        <input
          type="file"
          accept="image/*"
          capture="environment"
          multiple
          className="hidden"
          onChange={(e) => {
            onFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </label>
      {fileError && <p className="text-sm text-[#c8453f]">{fileError}</p>}
      <ErrorText error={scan.error} />
      {!review && (
        <button
          type="button"
          onClick={manual}
          className="self-start text-sm text-ink-2 hover:text-navy hover:underline"
        >
          <Pencil className="mr-1 inline size-3" />
          사진 인식이 안 되면 직접 입력하기
        </button>
      )}

      {review && (
        <>
          {review.missing.length > 0 && (
            <p role="status" className="rounded-xl bg-gold-soft px-4 py-3 text-sm text-[#6b4a0c]">
              답안지 {review.missing.join(', ')}쪽 사진이 없습니다. 그 쪽 문항은 직접 고르거나 다시
              찍어 주세요.
            </p>
          )}
          <p className="text-sm">
            인식한 답을 확인하세요.{' '}
            {needCheck > 0 && (
              <span className="text-[#8a6212]">
                표시된 칸 {needCheck}개는 비었거나 두 개 이상 칠해졌습니다.
              </span>
            )}
          </p>
          <div className="grid gap-1.5 sm:grid-cols-2">
            {review.mcq.map((m) => {
              const n = byId.get(m.problem_id)?.choices.length ?? 5
              return (
                <div
                  key={m.no}
                  className={cn(
                    'flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5',
                    m.status === 'ok' && 'border-home-line bg-white',
                    m.status === 'multiple' && 'border-2 border-[#c8453f] bg-[#fbeceb]',
                    (m.status === 'blank' || m.status === 'missing') && 'border-gold bg-[#fdf6e7]',
                  )}
                >
                  <span className="w-7 text-right text-sm font-bold">{m.no}</span>
                  {Array.from({ length: n }, (_, j) => (
                    <button
                      key={j}
                      type="button"
                      aria-label={`${m.no}번 ${j + 1}번 보기`}
                      aria-pressed={m.chosen === j}
                      onClick={() => pick(m.no, m.chosen === j ? null : j)}
                      className={cn(
                        'size-8 cursor-pointer rounded-full border text-xs font-bold',
                        m.chosen === j ? 'border-navy bg-navy text-white' : 'border-home-line bg-white',
                      )}
                    >
                      {j + 1}
                    </button>
                  ))}
                  {m.status === 'multiple' && <span className="text-xs font-bold text-[#c8453f]">두 개 칠함</span>}
                  {m.status === 'blank' && <span className="text-xs font-bold text-[#8a6212]">빈칸</span>}
                  {m.status === 'missing' && (
                    <span className="text-xs font-bold text-[#8a6212]">사진 없음</span>
                  )}
                </div>
              )
            })}
          </div>
          {review.essays.length > 0 && (
            <div className="flex flex-col gap-2">
              <div className="text-sm font-bold">서술형 답 (채점은 나중에)</div>
              {review.essays.map((e) => (
                <div key={e.no} className="flex flex-col gap-1">
                  <span className="text-sm font-semibold">{e.no}번</span>
                  {e.image ? (
                    <img
                      src={`data:image/jpeg;base64,${e.image}`}
                      alt={`${e.no}번 답`}
                      className="rounded-xl border border-home-line"
                    />
                  ) : (
                    <span className="text-xs text-ink-2">사진에서 찾지 못함</span>
                  )}
                </div>
              ))}
            </div>
          )}
          <ErrorText error={submit.error} />
          <button type="button" onClick={send} disabled={submit.isPending} className={cn(BTN.primary, 'h-12 self-end px-6 text-base')}>
            <Check />
            {submit.isPending ? '채점하는 중…' : '이대로 제출하고 채점하기'}
          </button>
        </>
      )}
    </section>
  )
}

function ResultView({ takeId, onBack }: { takeId: number; onBack: () => void }) {
  // 휴대폰에서 결과가 너무 길어 틀린 문제만 먼저 보여 주고, 맞힌 문제는 펼쳐 본다
  const [showAll, setShowAll] = useState(false)
  const result = useTakeResult(takeId)
  if (result.isPending) return <Loading />
  if (!result.data) return <ErrorText error={result.error} />
  const r = result.data
  const wrong = r.items.filter((i) => i.correct === false).length
  const grading = r.essay_status === 'pending'
  return (
    <div className="flex flex-col gap-4">
      <section className="flex flex-wrap items-center gap-7 rounded-3xl bg-navy-deep p-7 text-white sm:p-8">
        <div className="flex min-w-0 flex-[999_1_22rem] flex-col gap-3">
          <div className="text-sm text-[#c9d3e8]">
            걸린 시간 {mmss(r.elapsed_sec)} · 틀린 문제 {wrong}개
            {r.late && (
              <span className="ml-2 rounded-full bg-[#fdf0ef] px-2 py-0.5 text-xs font-bold text-[#a3352f]">
                시간 초과
              </span>
            )}
          </div>
          {r.summary ? (
            <p className="flex gap-2 text-lg font-bold leading-relaxed sm:text-xl">
              <Sparkles className="mt-1.5 size-5 shrink-0 text-gold" aria-hidden="true" />
              {r.summary}
            </p>
          ) : (
            r.essay_status !== 'unavailable' && <p className="text-[15px] text-[#c9d3e8]">요약을 만드는 중…</p>
          )}
          {grading && (
            <p className="flex items-center gap-1.5 text-sm text-gold">
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> 서술형 채점 중…{' '}
              <GradingClock since={r.submitted_at} /> (보통 30초~1분, 끝나면 점수·등수에 반영)
            </p>
          )}
          {r.essay_status === 'unavailable' && (
            <p className="text-sm text-gold">서술형은 채점 대기 중입니다(점수에 아직 안 들어감)</p>
          )}
          <div className="mt-1 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onBack}
              className="h-11 cursor-pointer rounded-full bg-white px-5 text-[15px] font-bold text-navy hover:bg-navy-tint"
            >
              다시 풀기 · 응시 기록
            </button>
          </div>
        </div>
        <div className="grid flex-[1_1_14rem] grid-cols-2 gap-3">
          <div className="rounded-2xl bg-white/10 p-4">
            <div className="text-[13px] text-[#c9d3e8]">점수</div>
            <div className="text-3xl font-bold tabular-nums">
              {r.score}
              <span className="text-base font-normal text-[#c9d3e8]"> / {r.total_points}</span>
            </div>
          </div>
          {r.rank != null && (
            <div className="rounded-2xl bg-white/10 p-4">
              <div className="text-[13px] text-[#c9d3e8]">등수</div>
              <div className="text-3xl font-bold tabular-nums">
                {r.rank}
                <span className="text-base font-normal text-[#c9d3e8]"> / {r.takers}명</span>
              </div>
            </div>
          )}
        </div>
      </section>
      {(r.report.repeated.length > 0 || r.report.review_pages.length > 0) && (
        <section className="grid gap-5 rounded-2xl border border-home-line bg-white p-5 md:grid-cols-2">
          {r.report.repeated.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-lg font-bold">반복된 오개념</h3>
              {r.report.repeated.map((l) => (
                <div
                  key={l.label}
                  className="flex items-center justify-between gap-3 rounded-xl bg-[#fdf6e7] px-4 py-3"
                >
                  <span className="text-sm font-bold text-[#4a3407]">{l.label}</span>
                  <span className="shrink-0 rounded-full bg-gold-soft px-2.5 py-0.5 text-xs font-bold text-[#6b4a0c]">
                    {l.count}문제
                  </span>
                </div>
              ))}
            </div>
          )}
          {r.report.review_pages.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-lg font-bold">다시 볼 교안</h3>
              {r.report.review_pages.slice(0, 5).map((p) => (
                <div
                  key={p}
                  className="flex h-11 items-center rounded-xl bg-navy-tint px-4 text-sm font-bold text-navy"
                >
                  {p}
                </div>
              ))}
            </div>
          )}
        </section>
      )}
      <Suspense fallback={<Loading />}>
        <ReportCharts report={r.report} />
      </Suspense>
      <h3 className="mt-2 text-xl font-bold">문제별 결과</h3>
      <ItemsToggle
        right={r.items.filter((i) => i.correct === true).length}
        showAll={showAll}
        onToggle={() => setShowAll((v) => !v)}
      />
      <div className="flex flex-col gap-3">
        {r.items.filter((i) => showAll || i.correct !== true).map((i) => (
          <article
            key={i.no}
            id={`q-${i.no}`}
            className={cn(
              CARD,
              'flex flex-col gap-2.5 p-5 text-[15px]',
              i.correct === false && 'border-[#c8453f]/40',
            )}
          >
            <div className="flex items-start gap-2">
              {i.correct === true ? (
                <Check className="size-5 shrink-0 text-[#2e8b6a]" />
              ) : i.correct === false ? (
                <X className="size-5 shrink-0 text-[#c8453f]" />
              ) : (
                <Clock className="size-5 shrink-0 text-ink-2" />
              )}
              <div className="whitespace-pre-wrap">
                <b>{i.no}.</b> {i.question}
              </div>
            </div>
            {i.qtype === 'mcq' ? (
              <div className="pl-7 text-sm text-ink-2">
                내 답 {i.chosen == null ? '없음' : `${i.chosen + 1}번`} · 정답 {i.answer_index + 1}
                번 ({i.choices[i.answer_index]})
              </div>
            ) : (
              <EssayDetail item={i} grading={grading} />
            )}
            {i.misconception && <MisconceptionBox m={i.misconception} />}
            {i.correct !== true && (
              <div className="ml-7 flex flex-col gap-2 rounded-xl bg-home-bg p-4 text-sm leading-relaxed">
                <p className="whitespace-pre-wrap">{i.explanation}</p>
                <Evidence evidence={i.evidence} source={i.source} />
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  )
}

type ResultItem = Schemas['ResultItem']

/** 제출한 지 몇 초 지났는지(채점 기다리는 동안 멈춘 게 아니라는 표시) */
function ItemsToggle({
  right,
  showAll,
  onToggle,
}: {
  right: number
  showAll: boolean
  onToggle: () => void
}) {
  if (!right) return null
  return (
    <button type="button" onClick={onToggle} className="cursor-pointer self-start text-sm font-bold text-navy hover:underline">
      {showAll ? '틀린 문제만 보기' : `맞힌 문제 ${right}개도 보기`}
    </button>
  )
}

function GradingClock({ since }: { since: string | null | undefined }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  if (!since) return null
  const t = new Date(since.endsWith('Z') || since.includes('+') ? since : `${since}Z`).getTime()
  return <span className="tabular-nums">{Math.max(0, Math.round((now - t) / 1000))}초</span>
}

function MisconceptionBox({ m }: { m: NonNullable<ResultItem['misconception']> }) {
  return (
    <div className="ml-7 flex flex-col gap-1.5 rounded-xl bg-gold-soft/60 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-white px-2.5 py-0.5 text-xs font-bold text-[#6b4a0c]">
          {m.status === 'approved' ? '확인된 오개념' : 'AI 추정'}
        </span>
        <b className="text-[#4a3407]">{m.label}</b>
      </div>
      <p>{m.hypothesis}</p>
      <p className="text-ink-2">{m.explanation}</p>
      {m.evidence && <Evidence evidence={m.evidence} source={m.source} />}
    </div>
  )
}

function EssayDetail({ item: i, grading }: { item: ResultItem; grading: boolean }) {
  return (
    <div className="flex flex-col gap-2 pl-7 text-sm">
      <div className="text-ink-2">
        서술형 ·{' '}
        {i.score != null ? (
          <b className="text-foreground">
            {i.score}/{i.points}점
          </b>
        ) : grading ? (
          '채점 중…'
        ) : (
          '채점 대기'
        )}
      </div>
      {i.transcription != null && (
        <div>
          <span className="text-xs text-ink-2">읽은 답</span>
          <p className="mt-1 whitespace-pre-wrap rounded-xl border border-home-line bg-white px-3 py-2">
            {i.transcription || '(비어 있음)'}
          </p>
        </div>
      )}
      {i.rubric && i.rubric.length > 0 && (
        <ul className="flex flex-col gap-1">
          {i.rubric.map((x) => (
            <li key={x.item} className="flex gap-2">
              <span className="w-12 shrink-0 tabular-nums font-medium">
                {x.points}/{x.max_points}
              </span>
              <span>
                {x.item}
                <span className="text-ink-2"> — {x.reason}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {i.feedback && <p className="text-ink-2">💬 {i.feedback}</p>}
      {i.model_answer && (
        <div className="whitespace-pre-wrap text-ink-2">모범답안: {i.model_answer}</div>
      )}
    </div>
  )
}

function Ranking({ paperId }: { paperId: number }) {
  const ranking = useRanking(paperId)
  if (ranking.isPending) return null
  const entries = ranking.data?.entries ?? []
  return (
    <div className="flex flex-col gap-2">
      <h2 className="flex items-center gap-2 text-xl font-bold">
        <Trophy className="size-5 text-gold" />이 시험지 등수
      </h2>
      <p className="text-[13px] text-ink-2">
        사람마다 첫 응시만, 점수 높은 순 → 걸린 시간 짧은 순입니다. 다른 사람은 익명입니다.
        {ranking.data?.essay_pending && ' 서술형 채점 대기가 있어 지금은 객관식 점수 기준입니다.'}
      </p>
      {entries.length === 0 ? (
        <Empty>아직 응시한 사람이 없습니다.</Empty>
      ) : (
        <div className={cn(CARD, 'overflow-hidden')}>
          <table className="w-full text-[15px]">
            <tbody className="divide-y divide-home-line">
              {entries.map((e) => (
                <tr
                  key={`${e.rank}-${e.label}`}
                  className={cn(e.me && 'bg-navy-tint font-bold text-navy')}
                >
                  <td className="w-16 px-5 py-3 text-right tabular-nums">{e.rank}등</td>
                  <td className="px-5 py-3">{e.label}</td>
                  <td className="px-5 py-3 text-right tabular-nums">
                    {e.score}/{e.total_points}
                  </td>
                  <td className="px-5 py-3 text-right text-sm text-ink-2">
                    {mmss(e.elapsed_sec)}
                    {e.late && ' · 시간 초과'}
                    {e.paused && ' · 일시정지 사용'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ErrorText error={ranking.error} />
    </div>
  )
}
