import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/api/client'

export const useSubjects = () =>
  useQuery({ queryKey: ['subjects'], queryFn: () => unwrap(api.GET('/api/v1/subjects')) })

export const useCourses = (subjectId: number) =>
  useQuery({
    queryKey: ['subjects', subjectId, 'courses'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/subjects/{subject_id}/courses', {
          params: { path: { subject_id: subjectId } },
        }),
      ),
  })

export const useCourse = (courseId: number) =>
  useQuery({
    queryKey: ['courses', courseId],
    queryFn: () =>
      unwrap(api.GET('/api/v1/courses/{course_id}', { params: { path: { course_id: courseId } } })),
  })
