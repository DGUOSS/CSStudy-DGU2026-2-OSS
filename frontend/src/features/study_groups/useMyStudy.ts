import { useQueries } from '@tanstack/react-query'
import { api, type Schemas, unwrap } from '@/api/client'
import { useAuth } from '@/features/auth/useAuth'
import { useMyCourses } from '@/features/enrollments/queries'

export type Study = Schemas['StudyOut']

/**
 * 내가 들어갈 수 있는 과목들의 스터디를 모은다 (홈 "내 스터디 그룹", 스터디 화면, 퀴즈 결과의 스터디 입구에서 씀).
 * "내 스터디 전체"를 주는 API가 없어서 과목마다 목록을 받아 합친다(과목 수만큼 요청).
 * subjectIds를 주면 그 과목만 본다.
 * - mine: 내가 개설했거나 참여 승인된 스터디
 * - recruiting: 모집 중이고 내가 아직 안 들어간 스터디 (약점이 겹치는 것부터)
 * - matched: recruiting 중 나와 약점이 겹치는 것
 */
export function useMyStudy(subjectIds?: number[]) {
  const { user } = useAuth()
  const mine = useMyCourses()
  const subjects = new Map<number, string>()
  for (const c of [...(mine.data?.courses ?? []), ...(mine.data?.public ?? [])]) subjects.set(c.subject_id, c.subject_name)
  const ids = subjectIds ?? [...subjects.keys()]

  const lists = useQueries({
    queries: ids.map((sid) => ({
      // 스터디 목록 화면의 key(['study-groups', 사용자, 과목, …])와 앞부분이 같아, 거기서 바뀌면 이것도 다시 받는다
      queryKey: ['study-groups', user?.id, sid, 'all50'],
      enabled: !!user,
      queryFn: () =>
        unwrap(
          api.GET('/api/v1/subjects/{subject_id}/study-groups', {
            params: { path: { subject_id: sid }, query: { state: 'all', offset: 0, limit: 50 } },
          }),
        ),
    })),
  })
  const all = lists.flatMap((q) => q.data?.items ?? [])
  const joined = all.filter((g) => g.is_mine || g.my_application === 'approved')
  const weak = (g: Study) => (g.shared_weak ?? []).length
  const recruiting = all
    .filter((g) => !g.closed_at && !joined.includes(g))
    .sort((a, b) => weak(b) - weak(a))
  return {
    subjects,
    mine: joined,
    recruiting,
    matched: recruiting.filter((g) => weak(g) > 0),
    loading: (subjectIds ? false : mine.isPending) || lists.some((q) => q.isPending),
  }
}

export const MODE_LABEL: Record<string, string> = { online: '온라인', offline: '오프라인', hybrid: '온·오프라인' }

export const peopleLabel = (g: Study) =>
  g.capacity ? `${g.participant_count}/${g.capacity}명` : `${g.participant_count}명`
