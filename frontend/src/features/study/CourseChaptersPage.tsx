import { ChevronDown, ChevronLeft, Play } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Empty, ErrorText, Loading } from '@/components/States'
import { useCourse } from '@/features/courses/queries'
import { ExamPicker } from '@/features/exams/ExamPicker'
import { AppShell } from '@/features/home/AppShell'
import { pct, useMastery } from '@/features/mastery/queries'
import { isForbidden } from '@/features/enrollments/queries'
import { cn } from '@/lib/utils'
import { useChapters } from './queries'

export const QUIZ_TOTAL = 8

/** 강좌의 챕터 선택(/study/courses/:courseId). 챕터별 숙련도를 누르면 개념별 숙련도가 펼쳐진다. */
export function CourseChaptersPage() {
  return (
    <AppShell>
      <ChaptersContent />
    </AppShell>
  )
}

function ChaptersContent() {
  const courseId = Number(useParams().courseId)
  const navigate = useNavigate()
  const course = useCourse(courseId)
  const chapters = useChapters(courseId)
  const mastery = useMastery(courseId)
  const [selected, setSelected] = useState<number[]>([])
  const [open, setOpen] = useState<number | null>(null)

  if (course.isPending || chapters.isPending) return <Loading />
  if (isForbidden(course.error))
    return (
      <Empty>
        수강 기록이 있는 강좌만 들어갈 수 있습니다.{' '}
        <Link to="/find" className="font-bold text-navy hover:underline">
          강좌 찾기
        </Link>
      </Empty>
    )
  if (!course.data) return <ErrorText error={course.error} />
  const c = course.data
  const list = chapters.data ?? []

  const toggle = (id: number) =>
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]))
  const start = () =>
    navigate(`/study/courses/${courseId}/quiz?chapters=${selected.join(',')}`)

  return (
    <>
      <div>
        <Link to="/study" className="mb-2 inline-flex items-center text-sm text-ink-2">
          <ChevronLeft className="size-4" />
          학습
        </Link>
        <h1 className="text-2xl font-bold">
          {c.subject_name} <span className="text-ink-2">·</span> {c.professor_name} 교수님
        </h1>
        <p className="mt-1 text-sm text-ink-2">
          풀고 싶은 단원을 고르세요. 숙련도를 누르면 개념별 숙련도를 볼 수 있어요.
        </p>
      </div>

      <details className="rounded-2xl border border-home-line bg-white p-4">
        <summary className="cursor-pointer text-[15px] font-bold">참고할 족보 고르기</summary>
        <div className="mt-3">
          <ExamPicker courseId={courseId} />
        </div>
      </details>

      {list.length === 0 ? (
        <Empty>아직 문제가 없습니다. 기존 화면의 자료 탭에서 교안을 올려 주세요.</Empty>
      ) : (
        <ul className="flex flex-col gap-3 pb-24">
          {list.map((ch) => {
            const concepts = mastery.data?.find((m) => m.chapter_id === ch.id)?.concepts ?? []
            const tried = concepts.filter((x) => x.attempts > 0)
            const avg = concepts.length
              ? tried.reduce((s, x) => s + x.mastery, 0) / concepts.length
              : 0
            const on = selected.includes(ch.id)
            const expanded = open === ch.id
            const empty = ch.problem_count === 0
            return (
              <li
                key={ch.id}
                className={cn(
                  'rounded-2xl border bg-white p-5 transition-colors',
                  on ? 'border-navy ring-2 ring-navy/15' : 'border-home-line',
                )}
              >
                <div className="flex items-start gap-4">
                  <input
                    type="checkbox"
                    checked={on}
                    disabled={empty}
                    onChange={() => toggle(ch.id)}
                    aria-label={`${ch.title} 선택`}
                    className="mt-1 size-5 shrink-0 cursor-pointer accent-navy disabled:cursor-not-allowed"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-bold">{ch.title}</p>
                    <p className="mt-0.5 text-sm text-ink-2">
                      {empty ? '문제 없음' : `문제 ${ch.problem_count}개`}
                    </p>
                    <button
                      type="button"
                      onClick={() => setOpen(expanded ? null : ch.id)}
                      aria-expanded={expanded}
                      className="mt-3 flex w-full max-w-sm cursor-pointer items-center gap-3 text-left"
                    >
                      <span className="h-2 flex-1 overflow-hidden rounded-full bg-[#e6eaf2]">
                        <span
                          className="block h-full rounded-full bg-navy"
                          style={{ width: `${Math.round(avg * 100)}%` }}
                        />
                      </span>
                      <span className="text-sm font-bold text-navy underline underline-offset-2">
                        숙련도 {pct(avg)}
                      </span>
                      <ChevronDown
                        size={16}
                        className={cn('text-navy transition-transform', expanded && 'rotate-180')}
                      />
                    </button>
                  </div>
                </div>

                {expanded && (
                  <div className="mt-4 flex flex-col gap-3 rounded-xl bg-home-bg p-4">
                    {concepts.length === 0 ? (
                      <p className="text-sm text-ink-2">이 챕터에는 아직 개념 정보가 없습니다.</p>
                    ) : (
                      concepts.map((x) => (
                        <div key={x.concept_id} className="grid gap-1">
                          <div className="flex justify-between text-sm">
                            <span>{x.name}</span>
                            <span className="text-ink-2">
                              {x.attempts === 0
                                ? '아직 안 풀었음'
                                : `${pct(x.mastery)} · ${x.correct}/${x.attempts}`}
                            </span>
                          </div>
                          <span className="h-1.5 w-full overflow-hidden rounded-full bg-white">
                            <span
                              className="block h-full rounded-full bg-gold"
                              style={{ width: `${x.attempts === 0 ? 0 : Math.round(x.mastery * 100)}%` }}
                            />
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
      <ErrorText error={chapters.error ?? mastery.error} />

      <div className="fixed inset-x-0 bottom-0 z-10 border-t border-home-line bg-white/95 backdrop-blur md:left-60">
        <div className="mx-auto flex max-w-[960px] items-center justify-between gap-4 px-6 py-4 lg:px-10">
          <p className="text-sm text-ink-2">
            {selected.length === 0 ? (
              '단원을 선택해 주세요'
            ) : (
              <>
                <b className="text-ink">{selected.length}개 단원</b> 선택 · 문제 최대 {QUIZ_TOTAL}개
              </>
            )}
          </p>
          <button
            type="button"
            disabled={selected.length === 0}
            onClick={start}
            className="inline-flex h-11 cursor-pointer items-center gap-2 rounded-full bg-navy px-6 text-[15px] font-bold text-white hover:bg-navy-deep disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Play size={16} />
            퀴즈 시작
          </button>
        </div>
      </div>
    </>
  )
}
