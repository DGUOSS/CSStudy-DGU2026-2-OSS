import { Navigate, useParams, useSearchParams } from 'react-router'

// 새 디자인이 켜져 있을 때, 새 화면이 따로 있는 옛 주소를 새 주소로 보낸다 (App.tsx에서 DESIGN_ON일 때만 씀)

// 옛 강좌 화면의 탭 이름 → 새 강좌 화면의 탭 이름 (문제 풀이·숙련도는 새 화면의 학습 탭 하나로 합쳐짐)
const TAB: Record<string, string | null> = {
  solve: null,
  mastery: null,
  papers: 'papers',
  materials: 'materials',
  info: 'info',
  groups: 'groups',
  reviews: 'reviews',
}

export function ToStudyCourse() {
  const { courseId } = useParams()
  const [params] = useSearchParams()
  const tab = TAB[params.get('tab') ?? 'solve'] ?? null
  return <Navigate to={`/study/courses/${courseId}${tab ? `?tab=${tab}` : ''}`} replace />
}

export function ToStudyQuiz() {
  const { courseId, chapterId } = useParams()
  return <Navigate to={`/study/courses/${courseId}/quiz?chapters=${chapterId}`} replace />
}

/** '/papers/:paperId' 같은 주소를 앞에 '/study'만 붙여 보낸다 */
export function ToStudy({ path }: { path: (p: Record<string, string | undefined>) => string }) {
  const params = useParams()
  return <Navigate to={path(params)} replace />
}
