import { ChevronLeft } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router'
import { Empty, ErrorText, Loading } from '@/components/States'
import { isForbidden } from '@/features/ndrims/queries'
import { cn } from '@/lib/utils'
import { MasteryTab } from '@/features/mastery/MasteryTab'
import { MaterialsTab } from '@/features/materials/MaterialsTab'
import { ChaptersTab } from '@/features/problems/ChaptersTab'
import { CourseInfoTab } from './CourseInfoTab'
import { useCourse } from './queries'

const TABS = [
  { key: 'solve', label: '문제 풀이' },
  { key: 'mastery', label: '숙련도' },
  { key: 'materials', label: '자료' },
  { key: 'info', label: '강좌 정보' },
] as const

type TabKey = (typeof TABS)[number]['key']

export function CoursePage() {
  const courseId = Number(useParams().courseId)
  const course = useCourse(courseId)
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as TabKey | null) ?? 'solve'

  if (course.isPending) return <Loading />
  if (isForbidden(course.error))
    return (
      <Empty>
        수강 기록이 있는 강좌만 들어갈 수 있습니다.{' '}
        <Link to="/" className="text-primary hover:underline">
          엔드림스에서 수강 기록 가져오기
        </Link>
      </Empty>
    )
  if (!course.data) return <ErrorText error={course.error} />
  const c = course.data

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link
          to={`/subjects/${c.subject_id}`}
          className="mb-2 inline-flex items-center text-sm text-muted-foreground"
        >
          <ChevronLeft className="size-4" />
          {c.subject_name}
        </Link>
        <h1 className="text-2xl font-bold">
          {c.subject_name} <span className="text-muted-foreground">·</span> {c.professor_name}{' '}
          교수님
        </h1>
      </div>
      <nav className="flex gap-1 overflow-x-auto border-b">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setParams({ tab: t.key }, { replace: true })}
            className={cn(
              '-mb-px cursor-pointer whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium',
              tab === t.key
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>
      {tab === 'solve' && <ChaptersTab courseId={courseId} />}
      {tab === 'mastery' && <MasteryTab courseId={courseId} />}
      {tab === 'materials' && <MaterialsTab courseId={courseId} />}
      {tab === 'info' && <CourseInfoTab course={c} />}
    </div>
  )
}
