import { useQuery } from '@tanstack/react-query'
import { ClipboardCheck, FileText } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { api, type Schemas, unwrap } from '@/api/client'
import { ExamPicker } from '@/features/exams/ExamPicker'
import { pct, useMastery } from '@/features/mastery/queries'
import { usePapers } from '@/features/papers/queries'
import { useMyStudy } from '@/features/study_groups/useMyStudy'
import { TeamYears } from '@/features/team_project/TeamYears'
import { cn } from '@/lib/utils'
import { useChapters } from './queries'

// 강좌 홈(시안 A): 왼쪽 "오늘 할 것"(퀴즈·모의고사), 오른쪽 "강좌 정보" 요약 카드(시험·평가+팀플, 강의평, 스터디, 자료).
// 요약 카드를 누르면 강좌 화면의 하위 화면(?tab=…)으로 간다. 데이터는 모두 기존 API.

type Course = Schemas['CourseOut']

/** 한 번이라도 푼 개념 중 숙련도가 가장 낮은 것(문제가 있는 단원만) */
function useWeakest(courseId: number) {
  const chapters = useChapters(courseId)
  const mastery = useMastery(courseId)
  const withProblems = new Set((chapters.data ?? []).filter((c) => c.problem_count > 0).map((c) => c.id))
  return (mastery.data ?? [])
    .flatMap((ch) => ch.concepts.filter((x) => x.attempts > 0).map((x) => ({ ...x, chapterId: ch.chapter_id })))
    .filter((x) => withProblems.has(x.chapterId))
    .sort((a, b) => a.mastery - b.mastery)[0]
}

const quizUrl = (courseId: number, ids: number[]) => `/study/courses/${courseId}/quiz?chapters=${ids.join(',')}`
const BTN_LIGHT =
  'inline-flex h-11 items-center rounded-full bg-white px-5 text-[15px] font-bold text-navy hover:bg-navy-tint'
const BTN_GHOST_DARK =
  'inline-flex h-11 items-center rounded-full border border-white/35 px-4 text-[15px] font-bold text-white hover:bg-white/10'
const BTN_NAVY = 'inline-flex h-11 items-center rounded-full bg-navy px-5 text-[15px] font-bold text-white hover:bg-navy-deep'
const BTN_OUTLINE =
  'inline-flex h-11 items-center rounded-full border border-home-line bg-white px-4 text-[15px] font-bold text-navy hover:bg-navy-tint'

/** 왼쪽 위 "오늘 할 것" 카드 두 장 */
export function TodayCards({ courseId }: { courseId: number }) {
  const navigate = useNavigate()
  const weakest = useWeakest(courseId)
  const papers = usePapers(courseId)
  const open = papers.data?.find((p) => p.my_open_take_id)
  const done = papers.data?.find((p) => p.my_best != null)

  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
      <section className="flex flex-col gap-3.5 rounded-3xl bg-navy-deep p-6 text-white">
        <div className="flex items-center gap-2.5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-white/10">
            <ClipboardCheck size={20} className="text-gold" aria-hidden="true" />
          </span>
          <h3 className="text-lg font-bold">퀴즈 풀기</h3>
        </div>
        {weakest ? (
          <>
            <p className="text-[15px] leading-relaxed text-[#dfe5f1]">
              가장 약한 개념 <b className="text-white">{weakest.name} {pct(weakest.mastery)}</b>부터 풀어 보세요
            </p>
            <span className="h-1.5 overflow-hidden rounded-full bg-white/15" aria-hidden="true">
              <span className="block h-full bg-gold" style={{ width: pct(weakest.mastery) }} />
            </span>
          </>
        ) : (
          <p className="text-[15px] leading-relaxed text-[#dfe5f1]">
            아직 푼 문제가 없어요. 아래에서 단원을 골라 시작해 보세요.
          </p>
        )}
        <div className="mt-auto flex flex-wrap gap-2">
          {weakest && (
            <button
              type="button"
              onClick={() => navigate(quizUrl(courseId, [weakest.chapterId]))}
              className={cn(BTN_LIGHT, 'cursor-pointer')}
            >
              약한 개념 풀기
            </button>
          )}
          <a href="#units" className={weakest ? BTN_GHOST_DARK : BTN_LIGHT}>
            단원 골라 풀기
          </a>
        </div>
      </section>

      <section className="flex flex-col gap-3.5 rounded-3xl border border-home-line bg-white p-6">
        <div className="flex items-center gap-2.5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-navy-tint">
            <FileText size={20} className="text-navy" aria-hidden="true" />
          </span>
          <h3 className="text-lg font-bold">모의고사</h3>
        </div>
        {open ? (
          <div className="rounded-xl bg-[#fdf6e7] px-3.5 py-3 text-sm">
            <b>{open.title}</b> 푸는 중
          </div>
        ) : (
          <p className="text-sm text-ink-2">
            종이에 인쇄해 시간을 재며 풀고, 답안지를 사진으로 찍어 채점해요.
          </p>
        )}
        {done && (
          <p className="text-sm text-ink-2">
            지난 결과: {done.title} {done.my_best}/{done.total_points}{' '}
            <Link to={`/study/papers/${done.id}`} className="font-bold text-navy hover:underline">
              리포트 ›
            </Link>
          </p>
        )}
        <div className="mt-auto flex flex-wrap gap-2">
          {open ? (
            <Link to={`/study/papers/${open.id}`} className={BTN_NAVY}>
              이어서 풀기
            </Link>
          ) : (
            <Link to={`/study/courses/${courseId}?tab=papers`} className={BTN_NAVY}>
              시험지 고르기
            </Link>
          )}
          <Link to={`/study/courses/${courseId}?tab=papers`} className={BTN_OUTLINE}>
            {open ? '시험지 목록' : '새 시험지'}
          </Link>
        </div>
      </section>
    </div>
  )
}

const CARD = 'flex flex-col gap-2 rounded-2xl border border-home-line bg-white px-[18px] py-4'
const CARD_LINK = cn(CARD, 'hover:border-navy/40')

function CardHead({ title, aside }: { title: string; aside?: string }) {
  return (
    <span className="flex items-baseline justify-between gap-2 text-[15px] font-bold">
      {title}
      <span className="text-sm font-normal text-ink-2">{aside ?? ''} ›</span>
    </span>
  )
}

/** 오른쪽 "강좌 정보" 요약 카드 묶음 */
export function CourseAside({ course }: { course: Course }) {
  const base = `/study/courses/${course.id}`
  return (
    <aside aria-label="강좌 정보" className="flex min-w-0 flex-col gap-3">
      <h2 className="text-xl font-bold">강좌 정보</h2>
      <InfoCard course={course} href={`${base}?tab=info`} />
      <ReviewsCard courseId={course.id} href={`${base}?tab=reviews`} />
      <StudyCard subjectId={course.subject_id} />
      <MaterialsCard courseId={course.id} href={`${base}?tab=materials`} />
    </aside>
  )
}

/** 시험·평가 + 팀플(최근 학기 라벨) */
function InfoCard({ course, href }: { course: Course; href: string }) {
  const text = (course.exam_info || course.info).trim()
  return (
    <div className={CARD}>
      <Link to={href} className="flex flex-col gap-2 hover:text-navy">
        <CardHead title="시험·평가" />
        <span className="line-clamp-3 text-sm leading-relaxed whitespace-pre-line text-[#364257]">
          {text || '아직 등록된 시험·평가 정보가 없어요.'}
        </span>
      </Link>
      <div className="flex flex-col gap-1.5 border-t border-home-line pt-2">
        <span className="text-[13px] font-bold text-ink-2">팀플</span>
        <TeamYears history={course.team_history} />
      </div>
    </div>
  )
}

function ReviewsCard({ courseId, href }: { courseId: number; href: string }) {
  // 강의평 목록 화면과 같은 주소를 쓰되, 요약용으로 최근 50개만 받아 평균을 낸다
  const reviews = useQuery({
    queryKey: ['courses', courseId, 'reviews', 'summary'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/courses/{course_id}/reviews', {
          params: { path: { course_id: courseId }, query: { offset: 0, limit: 50 } },
        }),
      ),
  })
  const list = reviews.data ?? []
  const avg = list.length ? list.reduce((s, r) => s + r.recommendation, 0) / list.length : 0
  const full = Math.round(avg)
  return (
    <Link to={href} className={CARD_LINK}>
      <CardHead title="강의평" aside={list.length ? `${list.length === 50 ? '최근 50' : list.length}개` : undefined} />
      {list.length === 0 ? (
        <span className="text-sm text-ink-2">아직 강의평이 없어요. 수강했다면 첫 강의평을 남겨 주세요.</span>
      ) : (
        <>
          <span className="flex items-center gap-2 text-sm">
            <b className="text-xl">{avg.toFixed(1)}</b>
            <span className="text-[#c9952d]" aria-label={`추천 별 5개 중 ${full}개`}>
              {'★'.repeat(full)}
              {'☆'.repeat(5 - full)}
            </span>
            <span className="text-ink-2">추천</span>
          </span>
          <span className="line-clamp-2 text-[13px] leading-normal text-ink-2">“{list[0].content}”</span>
        </>
      )}
    </Link>
  )
}

/** 스터디 카드: 내 스터디가 있으면 그것만(누르면 채팅) + 아래 작게 '다른 스터디 탐색', 없으면 '개설 스터디 확인하러 가기' 하나 */
function StudyCard({ subjectId }: { subjectId: number }) {
  const { mine, loading } = useMyStudy([subjectId])
  const list = `/study/subjects/${subjectId}/groups`
  return (
    <div className={CARD}>
      <span className="text-[15px] font-bold">스터디</span>
      {loading ? null : mine.length === 0 ? (
        <Link
          to={list}
          className="flex items-center justify-between rounded-xl bg-navy-tint px-3 py-2.5 text-sm font-bold text-navy hover:bg-tone-blue"
        >
          개설 스터디 확인하러 가기 <span aria-hidden="true">›</span>
        </Link>
      ) : (
        <>
          {mine.slice(0, 3).map((g) => (
            <Link
              key={g.id}
              to={`/study/groups/${g.id}`}
              className="flex items-center justify-between gap-2 rounded-xl bg-navy-tint px-3 py-2.5 text-sm font-bold text-navy hover:bg-tone-blue"
            >
              <span className="truncate">{g.title}</span>
              <span className="shrink-0" aria-hidden="true">›</span>
            </Link>
          ))}
          <Link to={list} className="self-start text-xs text-ink-2 hover:text-navy hover:underline">
            다른 스터디 탐색
          </Link>
        </>
      )}
    </div>
  )
}

function MaterialsCard({ courseId, href }: { courseId: number; href: string }) {
  // 자료 탭과 같은 key·주소 (react-query가 한 번만 받는다)
  const materials = useQuery({
    queryKey: ['courses', courseId, 'materials'],
    queryFn: () =>
      unwrap(api.GET('/api/v1/courses/{course_id}/materials', { params: { path: { course_id: courseId } } })),
  })
  const count = (k: string) => materials.data?.filter((m) => m.kind === k).length ?? 0
  return (
    <div className={CARD}>
      <Link to={href} className="flex flex-col gap-2 hover:text-navy">
        <CardHead title="자료" />
        <span className="text-sm text-[#364257]">
          교안 {count('lecture')} · 족보 {count('exam')} · 시험 정보 {count('note')}
        </span>
      </Link>
      <details className="border-t border-home-line pt-2">
        <summary className="cursor-pointer text-[13px] font-bold text-ink-2">출제 스타일로 쓸 족보 고르기</summary>
        <div className="mt-2">
          <ExamPicker courseId={courseId} />
        </div>
      </details>
    </div>
  )
}
