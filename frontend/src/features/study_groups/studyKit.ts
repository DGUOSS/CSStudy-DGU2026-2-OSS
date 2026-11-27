import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/api/client'
import { useAuth } from '@/features/auth/useAuth'
import type { Study } from './useMyStudy'

/** 새 디자인 스터디 화면들이 같이 쓰는 버튼 모양과 동작 */
export const btn = {
  primary:
    'inline-flex h-10 cursor-pointer items-center justify-center gap-1.5 rounded-full bg-navy px-4 text-sm font-bold text-white hover:bg-navy-deep disabled:cursor-default disabled:opacity-50',
  line: 'inline-flex h-10 cursor-pointer items-center justify-center gap-1.5 rounded-full border border-home-line bg-white px-4 text-sm font-bold text-navy hover:bg-navy-tint disabled:cursor-default disabled:opacity-50',
  quiet:
    'inline-flex h-10 cursor-pointer items-center justify-center rounded-full px-3 text-sm font-bold text-ink-2 hover:bg-home-bg hover:text-navy disabled:cursor-default disabled:opacity-50',
}

export const groupsKey = (userId: number | undefined, subjectId: number) => ['study-groups', userId, subjectId]

/** 신청·신청 취소·참여 취소(나가기) */
export function useParticipation(g: Study) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const params = { path: { subject_id: g.subject_id, group_id: g.id } }
  const done = () => qc.invalidateQueries({ queryKey: groupsKey(user?.id, g.subject_id) })
  return useMutation({
    mutationFn: (kind: 'apply' | 'cancel') =>
      kind === 'apply'
        ? unwrap(api.POST('/api/v1/subjects/{subject_id}/study-groups/{group_id}/apply', { params }))
        : unwrap(api.POST('/api/v1/subjects/{subject_id}/study-groups/{group_id}/cancel', { params })),
    onSettled: done,
  })
}
