import { createBrowserRouter, RouterProvider } from 'react-router'
import { Layout } from '@/components/Layout'
import { AdminCoursesPage } from '@/features/admin/AdminCoursesPage'
import { AdminMisconceptionProbesPage } from '@/features/admin/AdminMisconceptionProbesPage'
import { AuthPage } from '@/features/auth/AuthPage'
import { AdminRequestsPage } from '@/features/course_requests/AdminRequestsPage'
import { MyRequestsPage } from '@/features/course_requests/MyRequestsPage'
import { RequestCoursePage } from '@/features/course_requests/RequestCoursePage'
import { CoursePage } from '@/features/courses/CoursePage'
import { SubjectCoursesPage } from '@/features/courses/SubjectCoursesPage'
import { SubjectsPage } from '@/features/courses/SubjectsPage'
import { QuizPage } from '@/features/problems/QuizPage'
import { MisconceptionLabPage } from '@/features/problems/MisconceptionLabPage'

// 새 화면은 여기에 경로를 한 줄 추가한다
const router = createBrowserRouter([
  { path: '/login', element: <AuthPage mode="login" /> },
  { path: '/signup', element: <AuthPage mode="signup" /> },
  { path: '/lab/misconception', element: <MisconceptionLabPage /> },
  {
    element: <Layout />,
    children: [
      { path: '/', element: <SubjectsPage /> },
      { path: '/subjects/:subjectId', element: <SubjectCoursesPage /> },
      { path: '/courses/:courseId', element: <CoursePage /> },
      { path: '/courses/:courseId/chapters/:chapterId/quiz', element: <QuizPage /> },
      { path: '/requests', element: <MyRequestsPage /> },
      { path: '/requests/new', element: <RequestCoursePage /> },
      { path: '/admin/courses', element: <AdminCoursesPage /> },
      { path: '/admin/requests', element: <AdminRequestsPage /> },
      { path: '/admin/misconception-probes', element: <AdminMisconceptionProbesPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
