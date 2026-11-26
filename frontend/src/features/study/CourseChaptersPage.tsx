import { ChevronDown, ChevronLeft, Play } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { Empty, ErrorText, Loading } from '@/components/States'
import { CourseInfoTab } from '@/features/courses/CourseInfoTab'
import { useCourse } from '@/features/courses/queries'
import { isForbidden } from '@/features/enrollments/queries'
import { AppShell } from '@/features/home/AppShell'
import { ExamNotesPanel, MaterialsTab } from '@/features/materials/MaterialsTab'
import { pct, useMastery } from '@/features/mastery/queries'
import { PapersTab } from '@/features/papers/PapersTab'
import { ReviewsTab } from '@/features/reviews/ReviewsTab'
import { StudyList } from '@/features/study_groups/StudySubjectView'
import { TeamHistory } from '@/features/team_project/TeamHistory'
import { TeamReportPrompt } from '@/features/team_project/TeamReport'
import { cn } from '@/lib/utils'
import { CourseAside, TodayCards } from './CourseHub'
import { useChapters } from './queries'

export const QUIZ_TOTAL = 8

// 강좌 홈에서 들어가는 하위 화면(?tab=…). 옛 탭 주소도 그대로 열린다
const SUB = {
  papers: '시험지',
  materials: '자료',
  info: '시험·평가',
  reviews: '강의평',
  groups: '스터디',
} as const

type SubKey = keyof typeof SUB

/**
 * 강좌 화면(/study/courses/:courseId). 시안 A(강좌 홈): 왼쪽 "오늘 할 것"(퀴즈·모의고사)과 단원 고르기,
 * 오른쪽 "강좌 정보" 요약(시험·평가+팀플, 강의평, 스터디, 자료). 요약을 누르면 ?tab=… 하위 화면으로 간다.
 * 하위 화면은 기존 탭 컴포넌트를 그대로 쓴다.
 */
export function CourseChaptersPage() {
  return (
    <AppShell>
      <CourseContent />
    </AppShell>
  )
}

function CourseContent() {
  const courseId = Number(useParams().courseId)
  const course = useCourse(courseId)
  const [params] = useSearchParams()
  const raw = params.get('tab')
  const sub = raw && raw in SUB ? (raw as SubKey) : null

  if (course.isPending) return <Loading />
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
  const title = (
    <>
      {c.subject_name} <span className="text-ink-2">·</span> {c.professor_name} 교수님
    </>
  )

  if (sub)
    return (
      <>
        <div>
          <Link to={`/study/courses/${courseId}`} className="mb-2 inline-flex items-center text-sm text-ink-2">
            <ChevronLeft className="size-4" />
            {title}
          </Link>
          <h1 className="text-2xl font-bold">{SUB[sub]}</h1>
        </div>
        {sub === 'papers' && <PapersTab courseId={courseId} paperBase="/study/papers" />}
        {sub === 'materials' && <MaterialsTab courseId={courseId} />}
        {sub === 'info' && (
          <div className="flex flex-col gap-4">
            <CourseInfoTab course={c} examNotesHere />
            <ExamNotesPanel courseId={courseId} />
            <TeamHistory courseId={courseId} />
          </div>
        )}
        {sub === 'reviews' && <ReviewsTab key={courseId} courseId={courseId} />}
        {sub === 'groups' && <StudyList key={c.subject_id} subjectId={c.subject_id} withCreate />}
      </>
    )

  return (
    <>
      <div>
        <Link to="/study" className="mb-2 inline-flex items-center text-sm text-ink-2">
          <ChevronLeft className="size-4" />
          학습
        </Link>
        <h1 className="text-2xl font-bold">{title}</h1>
      </div>
      <TeamReportPrompt courseId={courseId} />

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex min-w-0 flex-col gap-5">
          <h2 className="text-xl font-bold">오늘 할 것</h2>
          <TodayCards courseId={courseId} />
          <LearnTab courseId={courseId} />
        </div>
        <CourseAside course={c} />
      </div>
    </>
  )
}

/** 단원 고르기: 단원별 숙련도(누르면 개념별로 펼침), 여러 단원을 골라 아래 고정 바에서 퀴즈 시작. */
function LearnTab({ courseId }: { courseId: number }) {
  const navigate = useNavigate()
  const chapters = useChapters(courseId)
  const mastery = useMastery(courseId)
  const [selected, setSelected] = useState<number[]>([])
  const [open, setOpen] = useState<number | null>(null)

  if (chapters.isPending) return <Loading />
  const list = chapters.data ?? []

  const toggle = (id: number) =>
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]))
  const quiz = (ids: number[]) => navigate(`/study/courses/${courseId}/quiz?chapters=${ids.join(',')}`)
  const pool = list.filter((ch) => selected.includes(ch.id)).reduce((s, ch) => s + ch.problem_count, 0)

  return (
    <>
      <div id="units" className="mt-2 flex scroll-mt-6 items-baseline justify-between gap-3">
        <h2 className="text-xl font-bold">단원 고르기</h2>
        <span className="text-sm text-ink-2">숙련도를 누르면 개념별로 펼쳐져요</span>
      </div>

      {list.length === 0 ? (
        <Empty>아직 문제가 없습니다. 자료 탭에서 교안을 올려 주세요.</Empty>
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
                      {empty && ch.essay_count === 0
                        ? '문제 없음'
                        : `객관식 ${ch.problem_count}개 · 서술형 ${ch.essay_count}개`}
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
                <b className="text-ink">단원 {selected.length}개</b> 선택 · 객관식 {pool}문제 중{' '}
                {Math.min(QUIZ_TOTAL, pool)}문제 출제
              </>
            )}
          </p>
          <button
            type="button"
            disabled={selected.length === 0}
            onClick={() => quiz(selected)}
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
