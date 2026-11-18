import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useAuth } from '@/features/auth/useAuth'
import { HomeSidebar } from './HomeSidebar'

/**
 * 새 디자인 화면의 공통 틀(사이드바 + 본문). Layout 밖에 두는 화면용이라 로그인 확인도 여기서 한다.
 * 로그인한 뒤에만 children을 그려서, 안쪽 화면은 API를 안전하게 부를 수 있다.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p className="p-8 text-center text-muted-foreground">불러오는 중…</p>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />

  return (
    <div className="flex min-h-svh bg-home-bg">
      <HomeSidebar />
      <main className="min-w-0 flex-1 px-6 pt-8 pb-12 lg:px-10">
        <div className="mx-auto flex max-w-[960px] flex-col gap-7">{children}</div>
      </main>
    </div>
  )
}
