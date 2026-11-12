import { createBrowserRouter, RouterProvider } from 'react-router'
import { Layout } from '@/components/Layout'
import { AdminCatalogPage } from '@/features/admin/AdminCatalogPage'
import { AdminCoursesPage } from '@/features/admin/AdminCoursesPage'
import { AuthPage } from '@/features/auth/AuthPage'
import { AdminRequestsPage } from '@/features/course_requests/AdminRequestsPage'
import { MyRequestsPage } from '@/features/course_requests/MyRequestsPage'
import { CoursePage } from '@/features/courses/CoursePage'
import { SubjectCoursesPage } from '@/features/courses/SubjectCoursesPage'
import { CatalogPage } from '@/features/ndrims/CatalogPage'
import { HomePage } from '@/features/ndrims/HomePage'
import { QuizPage } from '@/features/problems/QuizPage'

// 새 화면은 여기에 경로를 한 줄 추가한다
const router = createBrowserRouter([
  { path: '/login', element: <AuthPage mode="login" /> },
  { path: '/signup', element: <AuthPage mode="signup" /> },
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/find', element: <CatalogPage /> },
      { path: '/subjects/:subjectId', element: <SubjectCoursesPage /> },
      { path: '/courses/:courseId', element: <CoursePage /> },
      { path: '/courses/:courseId/chapters/:chapterId/quiz', element: <QuizPage /> },
      { path: '/requests', element: <MyRequestsPage /> },
      { path: '/admin/courses', element: <AdminCoursesPage /> },
      { path: '/admin/requests', element: <AdminRequestsPage /> },
      { path: '/admin/catalog', element: <AdminCatalogPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
