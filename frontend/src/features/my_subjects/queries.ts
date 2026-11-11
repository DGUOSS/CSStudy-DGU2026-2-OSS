import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, unwrap } from '@/api/client'

export type MyStatus = 'current' | 'taken'
export const STATUS_LABEL: Record<string, string> = { current: '수강 중', taken: '수강함' }

/** 내 과목(수강했거나 수강 중인 과목). 이 과목의 강좌에만 들어갈 수 있다. */
export const useMySubjects = () =>
  useQuery({
    queryKey: ['me', 'subjects'],
    queryFn: () => unwrap(api.GET('/api/v1/me/subjects')),
  })

export function useSetMySubject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ subjectId, status }: { subjectId: number; status: MyStatus }) =>
      unwrap(
        api.PUT('/api/v1/me/subjects/{subject_id}', {
          params: { path: { subject_id: subjectId } },
          body: { status },
        }),
      ),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useRemoveMySubject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (subjectId: number) =>
      unwrap(
        api.DELETE('/api/v1/me/subjects/{subject_id}', {
          params: { path: { subject_id: subjectId } },
        }),
      ),
    onSuccess: () => qc.invalidateQueries(),
  })
}

/** 내 과목에 없어서 막힌 경우(403) */
export const isForbidden = (e: Error | null) => e instanceof ApiError && e.status === 403
