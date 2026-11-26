import { ProfessorsPage } from '@/features/catalog/ProfessorsPage'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import { StudySpacePage } from '@/features/study_groups/StudySpacePage'
import { StudyGroupsPage } from '@/features/study_groups/StudyGroupsPage'
import { StudyHubPage } from '@/features/study_groups/StudyHubPage'
import { StudyRoomPage } from '@/features/study_groups/StudyRoomPage'
import { StudySubjectPage } from '@/features/study_groups/StudySubjectView'
import { Layout } from '@/components/Layout'
import { NotFound, RouteError } from '@/components/NotFound'
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
import { AppShell } from '@/features/home/AppShell'
import { ToStudy, ToStudyCourse, ToStudyQuiz } from '@/components/DesignRedirects'
import { DESIGN_ON } from '@/lib/design'
import { HomePage as DesignHomePage } from '@/features/home/HomePage'
import { PaperPage } from '@/features/papers/PaperPage'
import { PrintPage } from '@/features/papers/PrintPage'
import { QuizPage } from '@/features/problems/QuizPage'
import { CourseChaptersPage } from '@/features/study/CourseChaptersPage'
import { FindPage } from '@/features/study/FindPage'
import { ImportPage } from '@/features/study/ImportPage'
import { StudyQuizPage } from '@/features/study/QuizPage'
import { StudyPage } from '@/features/study/StudyPage'

// 내 컴퓨터에서만(.env.local에 VITE_DESIGN=on) 새 디자인으로 연다. 끄면 기존 화면 그대로 (lib/design.ts)
const designFirst = DESIGN_ON

// 새 화면은 여기에 경로를 한 줄 추가한다
const router = createBrowserRouter([
  {
    // 모든 화면의 오류·없는 주소는 개발자용 기본 화면 대신 안내 화면으로
    errorElement: <RouteError />,
    children: [
      { path: '/login', element: <AuthPage mode="login" /> },
      { path: '/signup', element: <AuthPage mode="signup" /> },
      { path: '/study/groups', element: <StudyHubPage /> },
      { path: '/study/groups/:groupId', element: <StudyRoomPage /> },
      { path: '/study/subjects/:subjectId/groups', element: <StudySubjectPage /> },
      { path: '/home', element: <DesignHomePage /> },
      { path: '/study', element: <StudyPage /> },
      { path: '/study/professors', element: <ProfessorsPage design /> },
      { path: '/study/find', element: <FindPage /> },
      { path: '/study/import', element: <ImportPage /> },
      { path: '/study/courses/:courseId', element: <CourseChaptersPage /> },
      { path: '/study/courses/:courseId/quiz', element: <StudyQuizPage /> },
      // 종이 시험(시험지·응시·결과)을 새 디자인 틀에서. 기존 /papers/:id는 그대로 둔다
      { path: '/study/papers/:paperId', element: <AppShell><PaperPage /></AppShell> },
      { path: '/study/papers/:paperId/print', element: <AppShell bare><PrintPage /></AppShell> },
      {
        element: <Layout />,
        children: [
          { path: '/subjects/:subjectId/groups', element: DESIGN_ON ? <ToStudy path={(p) => `/study/subjects/${p.subjectId}/groups`} /> : <StudyGroupsPage /> },
          { path: '/groups/:groupId', element: DESIGN_ON ? <ToStudy path={(p) => `/study/groups/${p.groupId}`} /> : <StudySpacePage /> },
          { path: '/', element: designFirst ? <Navigate to="/home" replace /> : <HomePage /> },
          { path: '/professors', element: DESIGN_ON ? <Navigate to="/study/professors" replace /> : <ProfessorsPage /> },
          { path: '/find', element: DESIGN_ON ? <Navigate to="/study/find" replace /> : <CatalogPage /> },
          { path: '/ndrims', element: <ReceivePage /> },
          { path: '/subjects/:subjectId', element: <SubjectCoursesPage /> },
          { path: '/courses/:courseId', element: DESIGN_ON ? <ToStudyCourse /> : <CoursePage /> },
          { path: '/courses/:courseId/chapters/:chapterId/quiz', element: DESIGN_ON ? <ToStudyQuiz /> : <QuizPage /> },
          { path: '/papers/:paperId', element: DESIGN_ON ? <ToStudy path={(p) => `/study/papers/${p.paperId}`} /> : <PaperPage /> },
          { path: '/papers/:paperId/print', element: DESIGN_ON ? <ToStudy path={(p) => `/study/papers/${p.paperId}/print`} /> : <PrintPage /> },
          { path: '/requests', element: <MyRequestsPage /> },
          { path: '/requests/new', element: <RequestCoursePage /> },
          { path: '/admin/courses', element: <AdminCoursesPage /> },
          { path: '/admin/requests', element: <AdminRequestsPage /> },
          { path: '/admin/catalog', element: <AdminCatalogPage /> },
          { path: '*', element: <NotFound /> },
        ],
      },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
