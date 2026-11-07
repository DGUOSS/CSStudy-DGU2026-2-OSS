import { createBrowserRouter, RouterProvider } from 'react-router'
import { Layout } from '@/components/Layout'
import { AuthPage } from '@/features/auth/AuthPage'
import { CoursePage } from '@/features/courses/CoursePage'
import { SubjectCoursesPage } from '@/features/courses/SubjectCoursesPage'
import { SubjectsPage } from '@/features/courses/SubjectsPage'
import { QuizPage } from '@/features/problems/QuizPage'

// 새 화면은 여기에 경로를 한 줄 추가한다
const router = createBrowserRouter([
  { path: '/login', element: <AuthPage mode="login" /> },
  { path: '/signup', element: <AuthPage mode="signup" /> },
  {
    element: <Layout />,
    children: [
      { path: '/', element: <SubjectsPage /> },
      { path: '/subjects/:subjectId', element: <SubjectCoursesPage /> },
      { path: '/courses/:courseId', element: <CoursePage /> },
      { path: '/courses/:courseId/chapters/:chapterId/quiz', element: <QuizPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
