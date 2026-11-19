import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import { StudySpacePage } from '@/features/study_groups/StudySpacePage'
import { StudyGroupsPage } from '@/features/study_groups/StudyGroupsPage'
import { Layout } from '@/components/Layout'
import { AdminCatalogPage } from '@/features/admin/AdminCatalogPage'
import { AdminCoursesPage } from '@/features/admin/AdminCoursesPage'
import { AuthPage } from '@/features/auth/AuthPage'
import { AdminRequestsPage } from '@/features/course_requests/AdminRequestsPage'
import { MyRequestsPage } from '@/features/course_requests/MyRequestsPage'
import { RequestCoursePage } from '@/features/course_requests/RequestCoursePage'
import { CoursePage } from '@/features/courses/CoursePage'
import { SubjectCoursesPage } from '@/features/courses/SubjectCoursesPage'
import { CatalogPage } from '@/features/catalog/CatalogPage'
import { HomePage } from '@/features/enrollments/HomePage'
import { ReceivePage } from '@/features/enrollments/ReceivePage'
import { HomePage as DesignHomePage } from '@/features/home/HomePage'
import { PaperPage } from '@/features/papers/PaperPage'
import { PrintPage } from '@/features/papers/PrintPage'
import { QuizPage } from '@/features/problems/QuizPage'
import { CourseChaptersPage } from '@/features/study/CourseChaptersPage'
import { FindPage } from '@/features/study/FindPage'
import { ImportPage } from '@/features/study/ImportPage'
import { StudyQuizPage } from '@/features/study/QuizPage'
import { StudyPage } from '@/features/study/StudyPage'

// 내 컴퓨터에서만(.env.local에 VITE_DESIGN=on) 첫 화면을 새 디자인으로 연다. 끄면 기존 화면 그대로
const designFirst = import.meta.env.VITE_DESIGN === 'on'

// 새 화면은 여기에 경로를 한 줄 추가한다
const router = createBrowserRouter([
  { path: '/login', element: <AuthPage mode="login" /> },
  { path: '/signup', element: <AuthPage mode="signup" /> },
  { path: '/study/groups/:groupId', element: <StudySpacePage design /> },
  { path: '/study/subjects/:subjectId/groups', element: <StudyGroupsPage design /> },
  { path: '/home', element: <DesignHomePage /> },
  { path: '/study', element: <StudyPage /> },
  { path: '/study/find', element: <FindPage /> },
  { path: '/study/import', element: <ImportPage /> },
  { path: '/study/courses/:courseId', element: <CourseChaptersPage /> },
  { path: '/study/courses/:courseId/quiz', element: <StudyQuizPage /> },
  {
    element: <Layout />,
    children: [
      { path: "/subjects/:subjectId/groups", element: <StudyGroupsPage /> },
      { path: "/groups/:groupId", element: <StudySpacePage /> },
      { path: '/', element: designFirst ? <Navigate to="/home" replace /> : <HomePage /> },
      { path: '/find', element: <CatalogPage /> },
      { path: '/ndrims', element: <ReceivePage /> },
      { path: '/subjects/:subjectId', element: <SubjectCoursesPage /> },
      { path: '/courses/:courseId', element: <CoursePage /> },
      { path: '/courses/:courseId/chapters/:chapterId/quiz', element: <QuizPage /> },
      { path: '/papers/:paperId', element: <PaperPage /> },
      { path: '/papers/:paperId/print', element: <PrintPage /> },
      { path: '/requests', element: <MyRequestsPage /> },
      { path: '/requests/new', element: <RequestCoursePage /> },
      { path: '/admin/courses', element: <AdminCoursesPage /> },
      { path: '/admin/requests', element: <AdminRequestsPage /> },
      { path: '/admin/catalog', element: <AdminCatalogPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
