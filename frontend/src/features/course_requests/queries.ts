import { useQuery } from '@tanstack/react-query'
import { api, type Schemas, unwrap } from '@/api/client'

export type CourseRequest = Schemas['CourseRequestOut']

export const STATUS_LABEL: Record<string, string> = {
  pending: '대기 중',
  approved: '승인',
  rejected: '반려',
}

export const useMyRequests = () =>
  useQuery({
    queryKey: ['course-requests', 'mine'],
    queryFn: () => unwrap(api.GET('/api/v1/course-requests/mine')),
  })

export const useAdminRequests = (status: 'pending' | 'approved' | 'rejected' | undefined) =>
  useQuery({
    queryKey: ['course-requests', 'admin', status ?? 'all'],
    queryFn: () =>
      unwrap(api.GET('/api/v1/admin/course-requests', { params: { query: { status } } })),
  })
