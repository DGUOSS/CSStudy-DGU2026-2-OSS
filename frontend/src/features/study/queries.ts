import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/api/client'

/** 과목의 강좌(교수) 목록. 키는 courses/queries.ts의 useCourses와 같아서 캐시를 같이 쓴다. */
export const subjectCoursesQuery = (subjectId: number) => ({
  queryKey: ['subjects', subjectId, 'courses'] as const,
  queryFn: () =>
    unwrap(
      api.GET('/api/v1/subjects/{subject_id}/courses', {
        params: { path: { subject_id: subjectId } },
      }),
    ),
})

/** 강좌의 챕터 목록. 키는 problems/ChaptersTab.tsx와 같다. */
export const useChapters = (courseId: number) =>
  useQuery({
    queryKey: ['courses', courseId, 'chapters'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/courses/{course_id}/chapters', {
          params: { path: { course_id: courseId } },
        }),
      ),
  })
