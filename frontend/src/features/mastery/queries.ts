import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/api/client'

export const useMastery = (courseId: number) =>
  useQuery({
    queryKey: ['courses', courseId, 'mastery'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/courses/{course_id}/mastery', {
          params: { path: { course_id: courseId } },
        }),
      ),
  })

/** 숙련도(0~1)를 퍼센트 문자열로 */
export const pct = (v: number) => `${Math.round(v * 100)}%`
