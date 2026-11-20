import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/api/client'

export const teamKey = (courseId: number) => ['courses', courseId, 'team-project']

export function useTeamProject(courseId: number) {
  return useQuery({
    queryKey: teamKey(courseId),
    queryFn: () => unwrap(api.GET('/api/v1/courses/{course_id}/team-project', {
      params: { path: { course_id: courseId } },
    })),
  })
}

type Answer = { year: string; sem_cd: string; team_project: boolean | null }

/** 결과로 받은 라벨로 화면을 바로 갱신하고, 목록·제목의 배지(강좌 정보)도 다시 받는다. */
function useOnSaved(courseId: number) {
  const qc = useQueryClient()
  return (data: unknown) => {
    qc.setQueryData(teamKey(courseId), data)
    void qc.invalidateQueries({ queryKey: ['courses', courseId], exact: true })
    void qc.invalidateQueries({ queryKey: ['subjects'] })
  }
}

export function useReportTeam(courseId: number) {
  const onSuccess = useOnSaved(courseId)
  return useMutation({
    mutationFn: (body: Answer) => unwrap(api.PUT('/api/v1/courses/{course_id}/team-project/report', {
      params: { path: { course_id: courseId } }, body,
    })),
    onSuccess,
  })
}

export function useOverrideTeam(courseId: number) {
  const onSuccess = useOnSaved(courseId)
  return useMutation({
    mutationFn: (body: Answer & { note: string }) => unwrap(api.PUT('/api/v1/admin/courses/{course_id}/team-project', {
      params: { path: { course_id: courseId } }, body,
    })),
    onSuccess,
  })
}
