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
import { Link, useParams } from 'react-router'
import type { Schemas } from '@/api/client'
import { Empty, ErrorText, Loading } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
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
  const [viewTake, setViewTake] = useState<number | null>(null)

  if (paper.isPending || mine.isPending) return <Loading />
  if (!paper.data || !mine.data) return <ErrorText error={paper.error ?? mine.error} />
  const p = paper.data
  const open = mine.data.open_take

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          to={`/courses/${p.course_id}?tab=papers`}
          className="mb-2 inline-flex items-center text-sm text-muted-foreground"
        >
          <ChevronLeft className="size-4" />
          시험 목록
        </Link>
        <h1 className="text-2xl font-bold">{p.title}</h1>
        <p className="text-sm text-muted-foreground">
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
        <Card className="flex flex-col gap-4 p-5">
          <ol className="list-decimal pl-5 text-sm text-muted-foreground">
            <li>
              시험지를 인쇄합니다(마지막 장이 답안지). 인쇄가 안 되면 답안지 이미지를 받아
              그림판이나 태블릿에서 표시해도 됩니다.
            </li>
            <li>
              준비되면 [시험 시작]을 누릅니다. 문제는 시작한 뒤 이 화면에서도 볼 수 있습니다. 답은
              답안지 동그라미에 칠하고, 서술형은 답 칸에 씁니다.
            </li>
            <li>
              끝나면 답안지를 사진(또는 이미지 파일)으로 올리고, 인식된 답을 확인해 제출합니다.
            </li>
          </ol>
          <div className="flex flex-wrap gap-2">
            <Link to={`/papers/${p.id}/print`} className={buttonVariants({ variant: 'outline' })}>
              <Printer />
              문제지·답안지 인쇄 / PDF
            </Link>
            <SheetDownload paperId={p.id} />
            <Button onClick={() => start.mutate()} disabled={start.isPending}>
              <Clock />
              시험 시작
            </Button>
          </div>
          <ErrorText error={start.error} />
        </Card>
      )}

      {!open && mine.data.submitted.length > 0 && (
        <div className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold">내 응시</h2>
          {mine.data.submitted.map((t, i) => (
            <button
              key={t.take_id}
              type="button"
              onClick={() => setViewTake(t.take_id)}
              className="flex cursor-pointer items-center justify-between rounded-lg border bg-card px-4 py-2 text-left text-sm hover:bg-accent"
            >
              <span>
                {i === mine.data.submitted.length - 1
                  ? '첫 응시'
                  : `${mine.data.submitted.length - i}번째`}{' '}
                · {new Date(t.submitted_at).toLocaleString()}
              </span>
              <span>
                <b>
                  {t.score}/{t.total_points}
                </b>
                {t.essay_pending && ' (서술형 채점 대기)'} · {mmss(t.elapsed_sec)}
                {t.late && ' · 시간 초과'}
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
      ? 'text-destructive'
      : level === 'warn'
        ? 'text-amber-600'
        : ''

  const timer = (
    <div className={cn('flex flex-col items-center gap-2', big && 'gap-6')}>
      <div className={cn('text-sm text-muted-foreground', big && 'text-xl')}>
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
          'h-2 w-full max-w-md overflow-hidden rounded-full bg-muted',
          big && 'h-3 max-w-3xl',
        )}
      >
        <div
          className={cn(
            'h-full transition-[width]',
            level === 'ok' ? 'bg-primary' : level === 'warn' ? 'bg-amber-500' : 'bg-destructive',
          )}
          style={{ width: `${spentRatio * 100}%` }}
        />
      </div>
      <div className={cn('text-center text-xs text-muted-foreground', big && 'text-base')}>
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
          <Button
            size={big ? 'lg' : 'default'}
            disabled={busy}
            onClick={() => resume.mutate(take.id)}
          >
            <Play />
            계속 풀기
          </Button>
        ) : (
          !over && (
            <Button
              variant="outline"
              size={big ? 'lg' : 'default'}
              disabled={busy}
              onClick={() => pause.mutate(take.id)}
            >
              <Pause />
              일시정지
            </Button>
          )
        )}
        <Button
          variant="outline"
          size={big ? 'lg' : 'default'}
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
        </Button>
        <Button
          variant="outline"
          size={big ? 'lg' : 'default'}
          onClick={() => {
            setBig(!big)
            if (!big) document.documentElement.requestFullscreen?.().catch(() => {})
            else if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
          }}
        >
          {big ? <Minimize2 /> : <Maximize2 />}
          {big ? '작게 보기' : '크게 보기'}
        </Button>
        {!submitting && (
          <Button
            size={big ? 'lg' : 'default'}
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
          </Button>
        )}
      </div>
    </div>
  )

  return (
    <div className="flex flex-col gap-4">
      {big ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background p-6">
          {timer}
        </div>
      ) : (
        <Card className={cn('p-6', over && 'border-destructive')}>{timer}</Card>
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
const CIRCLED = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧']

/** 시험 중 화면에서 보는 문제(인쇄를 못 했을 때). 정답은 없다. */
function Questions({ paper }: { paper: Paper }) {
  const [open, setOpen] = useState(true)
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center justify-between">
        <div className="font-semibold">
          문제{' '}
          <span className="font-normal text-muted-foreground">({paper.problems.length}문항)</span>
        </div>
        <Button size="sm" variant="ghost" onClick={() => setOpen(!open)}>
          {open ? '접기' : '펼치기'}
        </Button>
      </div>
      {open && (
        <ol className="flex flex-col gap-4 text-sm leading-relaxed">
          {paper.problems.map((q) => (
            <li key={q.id}>
              <div className="whitespace-pre-wrap">
                <b>{q.no}.</b> {q.question}{' '}
                <span className="text-xs text-muted-foreground">
                  ({q.points}점{q.qtype !== 'mcq' && ' · 서술형, 답안지 칸에 쓰세요'})
                </span>
              </div>
              {q.qtype === 'mcq' && (
                <div className="mt-1 grid gap-0.5 pl-4">
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
    </Card>
  )
}

function SheetDownload({ paperId }: { paperId: number }) {
  const sheet = useSheet(paperId)
  return (
    <Button
      variant="outline"
      disabled={!sheet.data}
      title="인쇄할 수 없을 때: 그림판·태블릿에서 칠하고 쓴 뒤 그대로 올리거나 화면을 찍어 올리세요"
      onClick={() => sheet.data && downloadSheetPngs(sheet.data.pages, paperId)}
    >
      <Download />
      답안지 이미지 받기
    </Button>
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
    <Card className="flex flex-col gap-4 p-5">
      <div>
        <div className="flex items-center justify-between">
          <div className="font-semibold">답안지 사진</div>
          <Button size="sm" variant="ghost" onClick={onCancel}>
            계속 풀기
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          네 귀퉁이의 검은 네모가 모두 나오게, 밝은 곳에서 위에서 찍어 주세요. 답안지가 여러 장이면
          장마다 한 장씩 함께 올립니다.
        </p>
      </div>
      <label
        className={cn(
          'flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-dashed px-4 py-6 text-sm hover:border-primary',
          scan.isPending && 'pointer-events-none opacity-60',
        )}
      >
        <Camera className="size-6 text-primary" />
        <span className="font-medium">
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
      {fileError && <p className="text-sm text-destructive">{fileError}</p>}
      <ErrorText error={scan.error} />
      {!review && (
        <button
          type="button"
          onClick={manual}
          className="self-start text-xs text-muted-foreground hover:underline"
        >
          <Pencil className="mr-1 inline size-3" />
          사진 인식이 안 되면 직접 입력하기
        </button>
      )}

      {review && (
        <>
          {review.missing.length > 0 && (
            <p className="rounded-md bg-amber-100 px-3 py-2 text-sm text-amber-900">
              답안지 {review.missing.join(', ')}쪽 사진이 없습니다. 그 쪽 문항은 직접 고르거나 다시
              찍어 주세요.
            </p>
          )}
          <p className="text-sm">
            인식한 답을 확인하세요.{' '}
            {needCheck > 0 && (
              <span className="text-amber-700">
                노란 칸 {needCheck}개는 비었거나 두 개 이상 칠해졌습니다.
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
                    'flex items-center gap-2 rounded-md border px-2 py-1',
                    m.status !== 'ok' && 'border-amber-400 bg-amber-50',
                  )}
                >
                  <span className="w-7 text-right text-sm font-semibold">{m.no}</span>
                  {Array.from({ length: n }, (_, j) => (
                    <button
                      key={j}
                      type="button"
                      onClick={() => pick(m.no, m.chosen === j ? null : j)}
                      className={cn(
                        'size-7 cursor-pointer rounded-full border text-xs',
                        m.chosen === j
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'bg-card',
                      )}
                    >
                      {j + 1}
                    </button>
                  ))}
                  {m.status === 'multiple' && <span className="text-xs text-amber-700">중복</span>}
                  {m.status === 'blank' && <span className="text-xs text-amber-700">빈칸</span>}
                  {m.status === 'missing' && (
                    <span className="text-xs text-amber-700">사진 없음</span>
                  )}
                </div>
              )
            })}
          </div>
          {review.essays.length > 0 && (
            <div className="flex flex-col gap-2">
              <div className="text-sm font-medium">서술형 답 (채점은 나중에)</div>
              {review.essays.map((e) => (
                <div key={e.no} className="flex flex-col gap-1">
                  <span className="text-sm font-semibold">{e.no}번</span>
                  {e.image ? (
                    <img
                      src={`data:image/jpeg;base64,${e.image}`}
                      alt={`${e.no}번 답`}
                      className="rounded border"
                    />
                  ) : (
                    <span className="text-xs text-muted-foreground">사진에서 찾지 못함</span>
                  )}
                </div>
              ))}
            </div>
          )}
          <ErrorText error={submit.error} />
          <Button onClick={send} disabled={submit.isPending}>
            <Check />
            {submit.isPending ? '채점하는 중…' : '이대로 제출하고 채점하기'}
          </Button>
        </>
      )}
    </Card>
  )
}

function ResultView({ takeId, onBack }: { takeId: number; onBack: () => void }) {
  const result = useTakeResult(takeId)
  if (result.isPending) return <Loading />
  if (!result.data) return <ErrorText error={result.error} />
  const r = result.data
  const wrong = r.items.filter((i) => i.correct === false).length
  const grading = r.essay_status === 'pending'
  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-center gap-6">
          <div>
            <div className="text-sm text-muted-foreground">점수</div>
            <div className="text-4xl font-bold tabular-nums">
              {r.score}
              <span className="text-lg text-muted-foreground">/{r.total_points}</span>
            </div>
          </div>
          {r.rank != null && (
            <div>
              <div className="text-sm text-muted-foreground">등수</div>
              <div className="text-2xl font-semibold tabular-nums">
                {r.rank}
                <span className="text-base text-muted-foreground">/{r.takers}명</span>
              </div>
            </div>
          )}
          <div className="text-sm">
            <div>
              걸린 시간 {mmss(r.elapsed_sec)}
              {r.late && (
                <Badge variant="outline" className="ml-2 border-destructive text-destructive">
                  시간 초과
                </Badge>
              )}
            </div>
            <div>틀린 문제 {wrong}개</div>
            {grading && (
              <div className="flex items-center gap-1 text-amber-700">
                <Loader2 className="size-3.5 animate-spin" /> 서술형 채점 중… (점수·등수에 곧 반영)
              </div>
            )}
            {r.essay_status === 'unavailable' && (
              <div className="text-amber-700">서술형은 채점 대기 중입니다(점수에 아직 안 들어감)</div>
            )}
          </div>
          <Button variant="outline" size="sm" className="ml-auto" onClick={onBack}>
            돌아가기
          </Button>
        </div>
        {r.summary ? (
          <div className="flex gap-2 rounded-lg bg-accent p-3 text-sm text-accent-foreground">
            <Sparkles className="mt-0.5 size-4 shrink-0" />
            <p>{r.summary}</p>
          </div>
        ) : (
          r.essay_status !== 'unavailable' && (
            <p className="text-xs text-muted-foreground">요약을 만드는 중…</p>
          )
        )}
        {(r.report.repeated.length > 0 || r.report.review_pages.length > 0) && (
          <div className="flex flex-col gap-1 text-sm">
            {r.report.repeated.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground">반복된 오개념</span>
                {r.report.repeated.map((l) => (
                  <Badge key={l.label} variant="outline" className="border-destructive/50">
                    {l.label} ×{l.count}
                  </Badge>
                ))}
              </div>
            )}
            {r.report.review_pages.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground">다시 볼 교안</span>
                {r.report.review_pages.slice(0, 5).map((p) => (
                  <Badge key={p} variant="secondary">
                    {p}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}
      </Card>
      <Suspense fallback={<Loading />}>
        <ReportCharts report={r.report} />
      </Suspense>
      <h3 className="mt-2 font-semibold">문제별 결과</h3>
      <div className="flex flex-col gap-3">
        {r.items.map((i) => (
          <Card
            key={i.no}
            className={cn(
              'flex flex-col gap-2 p-4 text-sm',
              i.correct === false && 'border-destructive/40',
            )}
          >
            <div className="flex items-start gap-2">
              {i.correct === true ? (
                <Check className="size-5 shrink-0 text-success" />
              ) : i.correct === false ? (
                <X className="size-5 shrink-0 text-destructive" />
              ) : (
                <Clock className="size-5 shrink-0 text-muted-foreground" />
              )}
              <div className="whitespace-pre-wrap">
                <b>{i.no}.</b> {i.question}
              </div>
            </div>
            {i.qtype === 'mcq' ? (
              <div className="pl-7 text-muted-foreground">
                내 답 {i.chosen == null ? '없음' : `${i.chosen + 1}번`} · 정답 {i.answer_index + 1}
                번 ({i.choices[i.answer_index]})
              </div>
            ) : (
              <EssayDetail item={i} grading={grading} />
            )}
            {i.misconception && <MisconceptionBox m={i.misconception} />}
            {i.correct !== true && (
              <div className="ml-7 flex flex-col gap-2 rounded-lg bg-muted p-3">
                <p className="whitespace-pre-wrap">{i.explanation}</p>
                <Evidence evidence={i.evidence} source={i.source} />
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}

type ResultItem = Schemas['ResultItem']

function MisconceptionBox({ m }: { m: NonNullable<ResultItem['misconception']> }) {
  return (
    <div className="ml-7 flex flex-col gap-1.5 rounded-lg border border-blue-600/30 bg-blue-600/5 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="border-blue-600/50 text-blue-700">
          {m.status === 'approved' ? '확인된 오개념' : 'AI 추정'}
        </Badge>
        <b>{m.label}</b>
      </div>
      <p>{m.hypothesis}</p>
      <p className="text-muted-foreground">{m.explanation}</p>
      {m.evidence && <Evidence evidence={m.evidence} source={m.source} />}
    </div>
  )
}

function EssayDetail({ item: i, grading }: { item: ResultItem; grading: boolean }) {
  return (
    <div className="flex flex-col gap-2 pl-7">
      <div className="text-muted-foreground">
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
          <span className="text-xs text-muted-foreground">읽은 답</span>
          <p className="whitespace-pre-wrap rounded-md border bg-card px-2 py-1">
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
                <span className="text-muted-foreground"> — {x.reason}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {i.feedback && <p className="text-muted-foreground">💬 {i.feedback}</p>}
      {i.model_answer && (
        <div className="whitespace-pre-wrap text-muted-foreground">모범답안: {i.model_answer}</div>
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
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        <Trophy className="size-5 text-primary" />이 시험지 등수
      </h2>
      <p className="text-xs text-muted-foreground">
        사람마다 첫 응시만, 점수 높은 순 → 걸린 시간 짧은 순입니다. 다른 사람은 익명입니다.
        {ranking.data?.essay_pending && ' 서술형 채점 대기가 있어 지금은 객관식 점수 기준입니다.'}
      </p>
      {entries.length === 0 ? (
        <Empty>아직 응시한 사람이 없습니다.</Empty>
      ) : (
        <div className="overflow-hidden rounded-xl border bg-card">
          <table className="w-full text-sm">
            <tbody className="divide-y">
              {entries.map((e) => (
                <tr
                  key={`${e.rank}-${e.label}`}
                  className={cn(e.me && 'bg-primary/5 font-semibold')}
                >
                  <td className="w-14 px-4 py-2 text-right">{e.rank}등</td>
                  <td className="px-4 py-2">{e.label}</td>
                  <td className="px-4 py-2 text-right">
                    {e.score}/{e.total_points}
                  </td>
                  <td className="px-4 py-2 text-right text-muted-foreground">
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
